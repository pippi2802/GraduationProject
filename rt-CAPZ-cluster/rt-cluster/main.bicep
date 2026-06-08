metadata description = 'Simple Kubernetes cluster on Azure - VMs, VNet, NSG only'

// Parameters
param location string = 'swedencentral'
param clusterName string = 'rt-cluster'
param controlPlaneCount int = 1
param workerNodeCount int = 1
param vmSize string = 'Standard_D4ds_v5'
param adminUsername string = 'azureuser'
@minLength(12)
@secure()
param adminPassword string
param sshPublicKey string = ''
param environment string = 'test'

// Image parameters
param imageSubscriptionId string = 'd06f8f89-f7d3-46b3-b7a8-649244fb54c6'
param imageResourceGroup string = 'rg-rtAKS'
param imageGallery string = 'rtUbuntu'
param imageName string = 'rtUbuntu24.04'
param imageVersion string = '1.0.2'

var vnetName = '${clusterName}-vnet'
var controlPlaneSubnetName = 'control-plane-subnet'
var workerSubnetName = 'node-subnet'
var nsgName = '${clusterName}-nsg'

// Virtual Network
resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.0.0.0/16'
      ]
    }
    subnets: [
      {
        name: controlPlaneSubnetName
        properties: {
          addressPrefix: '10.0.1.0/24'
          networkSecurityGroup: {
            id: nsg.id
          }
        }
      }
      {
        name: workerSubnetName
        properties: {
          addressPrefix: '10.0.2.0/24'
          networkSecurityGroup: {
            id: nsg.id
          }
        }
      }
    ]
  }
}

// Network Security Group
resource nsg 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: nsgName
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowSSH'
        properties: {
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '22'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
          access: 'Allow'
          priority: 100
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowKubernetes'
        properties: {
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '6443'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
          access: 'Allow'
          priority: 110
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowInternal'
        properties: {
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '10.0.0.0/16'
          destinationAddressPrefix: '10.0.0.0/16'
          access: 'Allow'
          priority: 120
          direction: 'Inbound'
        }
      }
    ]
  }
}

// Control Plane Network Interfaces
resource controlPlaneNIC 'Microsoft.Network/networkInterfaces@2023-11-01' = [for i in range(0, controlPlaneCount): {
  name: '${clusterName}-cp-${i}-nic'
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: '${vnet.id}/subnets/${controlPlaneSubnetName}'
          }
          privateIPAllocationMethod: 'Dynamic'
        }
      }
    ]
  }
}]

// Control Plane VMs
resource controlPlaneVM 'Microsoft.Compute/virtualMachines@2023-07-01' = [for i in range(0, controlPlaneCount): {
  name: '${clusterName}-cp-${i}'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    osProfile: {
      computerName: '${clusterName}-cp-${i}'
      adminUsername: adminUsername
      adminPassword: adminPassword
      linuxConfiguration: {
        disablePasswordAuthentication: !empty(sshPublicKey)
        ssh: empty(sshPublicKey) ? null : {
          publicKeys: [
            {
              path: '/home/${adminUsername}/.ssh/authorized_keys'
              keyData: sshPublicKey
            }
          ]
        }
      }
    }
    storageProfile: {
      imageReference: {
        id: '/subscriptions/${imageSubscriptionId}/resourceGroups/${imageResourceGroup}/providers/Microsoft.Compute/galleries/${imageGallery}/images/${imageName}/versions/${imageVersion}'
      }
      osDisk: {
        createOption: 'FromImage'
        diskSizeGB: 128
        managedDisk: {
          storageAccountType: 'Premium_LRS'
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: controlPlaneNIC[i].id
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
  tags: {
    role: 'control-plane'
    environment: environment
  }
}]

// Worker Node Network Interfaces
resource workerNIC 'Microsoft.Network/networkInterfaces@2023-11-01' = [for i in range(0, workerNodeCount): {
  name: '${clusterName}-worker-${i}-nic'
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: '${vnet.id}/subnets/${workerSubnetName}'
          }
          privateIPAllocationMethod: 'Dynamic'
        }
      }
    ]
  }
}]

// Worker Node VMs
resource workerVM 'Microsoft.Compute/virtualMachines@2023-07-01' = [for i in range(0, workerNodeCount): {
  name: '${clusterName}-worker-${i}'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    osProfile: {
      computerName: '${clusterName}-worker-${i}'
      adminUsername: adminUsername
      adminPassword: adminPassword
      linuxConfiguration: {
        disablePasswordAuthentication: !empty(sshPublicKey)
        ssh: empty(sshPublicKey) ? null : {
          publicKeys: [
            {
              path: '/home/${adminUsername}/.ssh/authorized_keys'
              keyData: sshPublicKey
            }
          ]
        }
      }
    }
    storageProfile: {
      imageReference: {
        id: '/subscriptions/${imageSubscriptionId}/resourceGroups/${imageResourceGroup}/providers/Microsoft.Compute/galleries/${imageGallery}/images/${imageName}/versions/${imageVersion}'
      }
      osDisk: {
        createOption: 'FromImage'
        diskSizeGB: 128
        managedDisk: {
          storageAccountType: 'Premium_LRS'
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: workerNIC[i].id
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
  tags: {
    role: 'worker'
    environment: environment
  }
}]

// Outputs
output clusterName string = clusterName
output location string = location
output vnetId string = vnet.id
output controlPlaneVMIds array = [for i in range(0, controlPlaneCount): controlPlaneVM[i].id]
output workerVMIds array = [for i in range(0, workerNodeCount): workerVM[i].id]
output nsgId string = nsg.id
