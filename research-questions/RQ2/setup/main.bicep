metadata description = 'Add extra worker VMs to the existing rt-k8s cluster (rg-RT-cluster) for RQ2. Does NOT touch the VNet/NSG/NAT/existing VMs - it only reads the existing VNet by name and adds new NICs + VMs into the existing worker subnet.'

// ----------------------------------------------------------------------------
// Cluster identity - must match the already-deployed cluster
// (setup/rt-cluster/parameters.json: clusterName "rt-k8s", worker subnet
// "worker-subnet" inside "rt-k8s-vnet", workerNodeCount 6 -> existing
// workers are rt-k8s-worker-0..5, so these new ones continue at index 6).
// ----------------------------------------------------------------------------
@description('Azure region - must match the existing cluster.')
param location string = resourceGroup().location

@description('Base name of the existing cluster (used to look up the existing VNet).')
param clusterName string = 'rt-k8s'

@description('Environment tag, same convention as the rest of the cluster.')
param environment string = 'dev'

@description('Extra tags, merged with the built-ins.')
param extraTags object = {}

// ----------------------------------------------------------------------------
// New workers
// ----------------------------------------------------------------------------
@description('How many new worker VMs to add.')
@minValue(1)
param newWorkerCount int = 2

@description('Worker index of the first new VM (existing workers are 0..workerNodeCount-1; default continues right after them).')
param startIndex int = 6

@description('VM size for the new workers.')
param workerVmSize string = 'Standard_D8ds_v5'

@description('Availability zones to round-robin the new VMs across - same list as the rest of the cluster.')
param zones array = [
  1
  2
  3
]

// ----------------------------------------------------------------------------
// Authentication - same values you used for the original cluster deployment
// ----------------------------------------------------------------------------
@description('Admin username - must match the existing VMs.')
param adminUsername string = 'azureuser'

@description('Admin password. Used only when sshPublicKey is empty.')
@minLength(12)
@secure()
param adminPassword string

@description('SSH public key. When non-empty, password authentication is disabled.')
param sshPublicKey string = ''

// ----------------------------------------------------------------------------
// Image - same shared image gallery as the existing workers
// (setup/rt-cluster/parameters.json)
// ----------------------------------------------------------------------------
@description('Subscription ID hosting the shared image gallery.')
param imageSubscriptionId string = 'f4ba420a-9799-4a43-bb7d-7fd76761e7a1'

@description('Resource group of the shared image gallery.')
param imageResourceGroup string = 'rg-rt-k8s'

@description('Shared image gallery name.')
param imageGallery string = 'rtUbuntu'

@description('Image definition name.')
param imageName string = 'rt-Ubuntu22.04'

@description('Image version.')
param imageVersion string = '1.0.0'

@description('OS disk size in GB - same as the existing workers.')
param osDiskSizeGB int = 64

@description('OS disk storage account type - same as the existing workers.')
param osDiskStorageAccountType string = 'Standard_LRS'

@description('Enable accelerated networking - same as the existing workers.')
param enableAcceleratedNetworking bool = true

// ----------------------------------------------------------------------------
// Computed values
// ----------------------------------------------------------------------------
var commonTags = union({
  cluster: clusterName
  environment: environment
  managedBy: 'bicep'
  addedFor: 'RQ2'
}, extraTags)

var imageReference = {
  id: '/subscriptions/${imageSubscriptionId}/resourceGroups/${imageResourceGroup}/providers/Microsoft.Compute/galleries/${imageGallery}/images/${imageName}/versions/${imageVersion}'
}

var useSshKey = !empty(sshPublicKey)
var vnetName = '${clusterName}-vnet'
var workerSubnetName = 'worker-subnet'

// ----------------------------------------------------------------------------
// Existing network - looked up by name, never recreated/modified.
// ----------------------------------------------------------------------------
resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' existing = {
  name: vnetName
}

var workerSubnetId = '${vnet.id}/subnets/${workerSubnetName}'

// ----------------------------------------------------------------------------
// New worker NICs + VMs - same shape as setup/rt-cluster/modules/vm.bicep,
// just named to continue the existing worker-N sequence.
// ----------------------------------------------------------------------------
resource nic 'Microsoft.Network/networkInterfaces@2023-11-01' = [for i in range(0, newWorkerCount): {
  name: '${clusterName}-worker-${startIndex + i}-nic'
  location: location
  tags: commonTags
  properties: {
    enableAcceleratedNetworking: enableAcceleratedNetworking
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: workerSubnetId
          }
          privateIPAllocationMethod: 'Dynamic'
        }
      }
    ]
  }
}]

resource vm 'Microsoft.Compute/virtualMachines@2023-09-01' = [for i in range(0, newWorkerCount): {
  name: '${clusterName}-worker-${startIndex + i}'
  location: location
  tags: union(commonTags, { role: 'worker' })
  zones: [string(zones[(startIndex + i) % length(zones)])]
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    hardwareProfile: {
      vmSize: workerVmSize
    }
    osProfile: {
      computerName: '${clusterName}-worker-${startIndex + i}'
      adminUsername: adminUsername
      adminPassword: useSshKey ? null : adminPassword
      linuxConfiguration: {
        disablePasswordAuthentication: useSshKey
        ssh: useSshKey ? {
          publicKeys: [
            {
              path: '/home/${adminUsername}/.ssh/authorized_keys'
              keyData: sshPublicKey
            }
          ]
        } : null
      }
    }
    storageProfile: {
      imageReference: imageReference
      osDisk: {
        createOption: 'FromImage'
        diskSizeGB: osDiskSizeGB
        managedDisk: {
          storageAccountType: osDiskStorageAccountType
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic[i].id
          properties: {
            primary: true
          }
        }
      ]
    }
    securityProfile: {
      securityType: 'TrustedLaunch'
      uefiSettings: {
        vTpmEnabled: true
        secureBootEnabled: false
      }
    }
  }
}]

// ----------------------------------------------------------------------------
// Outputs
// ----------------------------------------------------------------------------
output vmNames array = [for i in range(0, newWorkerCount): vm[i].name]
output privateIps array = [for i in range(0, newWorkerCount): nic[i].properties.ipConfigurations[0].properties.privateIPAddress]
