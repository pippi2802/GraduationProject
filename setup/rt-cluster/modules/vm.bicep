metadata description = 'Pool of identical Linux VMs (control plane or worker) with optional LB attachment and zone spread'

@description('Azure region.')
param location string

@description('Name prefix for VMs and NICs (e.g. "my-cluster-cp" or "my-cluster-worker").')
param namePrefix string

@description('Number of VMs to create.')
@minValue(1)
param count int

@description('VM size, e.g. Standard_D4ds_v5.')
param vmSize string

@description('Subnet ID where the NICs will be attached.')
param subnetId string

@description('Admin username for the VMs.')
param adminUsername string

@description('Admin password. Used only when sshPublicKey is empty.')
@secure()
param adminPassword string

@description('SSH public key. When non-empty, password authentication is disabled.')
param sshPublicKey string = ''

@description('Image reference object. Either { id: <gallery image id> } or { publisher, offer, sku, version }.')
param imageReference object

@description('OS disk size in GB.')
param osDiskSizeGB int = 128

@description('OS disk storage account type.')
param osDiskStorageAccountType string = 'Premium_LRS'

@description('Availability zones to spread VMs across (round-robin). Empty array => no zone.')
param zones array = []

@description('Backend address pool IDs to attach the primary NIC to. Empty array => not attached to any LB.')
param loadBalancerBackendPoolIds array = []

@description('Free-form tags applied to every resource.')
param tags object = {}

@description('Enable accelerated networking on NICs (requires a supported VM size).')
param enableAcceleratedNetworking bool = true

var useSshKey = !empty(sshPublicKey)
var hasZones  = !empty(zones)

resource nic 'Microsoft.Network/networkInterfaces@2023-11-01' = [for i in range(0, count): {
  name: '${namePrefix}-${i}-nic'
  location: location
  tags: tags
  properties: {
    enableAcceleratedNetworking: enableAcceleratedNetworking
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: subnetId
          }
          privateIPAllocationMethod: 'Dynamic'
          loadBalancerBackendAddressPools: [for poolId in loadBalancerBackendPoolIds: {
            id: poolId
          }]
        }
      }
    ]
  }
}]

resource vm 'Microsoft.Compute/virtualMachines@2023-09-01' = [for i in range(0, count): {
  name: '${namePrefix}-${i}'
  location: location
  tags: tags
  zones: hasZones ? [string(zones[i % length(zones)])] : null
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    osProfile: {
      computerName: '${namePrefix}-${i}'
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

output vmIds     array = [for i in range(0, count): vm[i].id]
output vmNames   array = [for i in range(0, count): vm[i].name]
output nicIds    array = [for i in range(0, count): nic[i].id]
output privateIps array = [for i in range(0, count): nic[i].properties.ipConfigurations[0].properties.privateIPAddress]
