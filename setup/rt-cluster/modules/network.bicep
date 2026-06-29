metadata description = 'VNet, subnets, NSG and NAT Gateway for the k8s cluster'

@description('Azure region for the network resources.')
param location string

@description('Base name used to derive resource names.')
param clusterName string

@description('CIDR for the virtual network.')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('CIDR for the control plane subnet.')
param controlPlaneSubnetPrefix string = '10.0.1.0/24'

@description('CIDR for the worker subnet.')
param workerSubnetPrefix string = '10.0.2.0/24'

@description('Tags applied to every resource.')
param tags object = {}

var vnetName = '${clusterName}-vnet'
var nsgName  = '${clusterName}-nsg'
var natName  = '${clusterName}-nat'
var natPipName = '${clusterName}-nat-pip'
var controlPlaneSubnetName = 'control-plane-subnet'
var workerSubnetName       = 'worker-subnet'

// ---------------------------------------------------------------------------
// NSG - only allow internal vnet traffic; egress is unrestricted (NAT GW).
// Inbound SSH / API server are reached either from inside the VNet (Bastion,
// `az ssh vm`) or via the load balancer, never directly from the internet.
// ---------------------------------------------------------------------------
resource nsg 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: nsgName
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowVnetSSHInbound'
        properties: {
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '22'
          sourceAddressPrefix: 'VirtualNetwork'
          destinationAddressPrefix: 'VirtualNetwork'
          access: 'Allow'
          priority: 100
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowVnetKubeApiInbound'
        properties: {
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '6443'
          sourceAddressPrefix: 'VirtualNetwork'
          destinationAddressPrefix: 'VirtualNetwork'
          access: 'Allow'
          priority: 110
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowVnetInternal'
        properties: {
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: 'VirtualNetwork'
          destinationAddressPrefix: 'VirtualNetwork'
          access: 'Allow'
          priority: 120
          direction: 'Inbound'
        }
      }
      {
        name: 'AllowAzureLBInbound'
        properties: {
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: 'AzureLoadBalancer'
          destinationAddressPrefix: '*'
          access: 'Allow'
          priority: 130
          direction: 'Inbound'
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// NAT Gateway + Public IP - gives every VM stable, secure outbound internet
// access without exposing any VM with a public endpoint.
// ---------------------------------------------------------------------------
resource natPip 'Microsoft.Network/publicIPAddresses@2023-11-01' = {
  name: natPipName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
    publicIPAddressVersion: 'IPv4'
  }
}

resource natGateway 'Microsoft.Network/natGateways@2023-11-01' = {
  name: natName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    idleTimeoutInMinutes: 10
    publicIpAddresses: [
      {
        id: natPip.id
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: controlPlaneSubnetName
        properties: {
          addressPrefix: controlPlaneSubnetPrefix
          networkSecurityGroup: {
            id: nsg.id
          }
          natGateway: {
            id: natGateway.id
          }
        }
      }
      {
        name: workerSubnetName
        properties: {
          addressPrefix: workerSubnetPrefix
          networkSecurityGroup: {
            id: nsg.id
          }
          natGateway: {
            id: natGateway.id
          }
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output controlPlaneSubnetId string = '${vnet.id}/subnets/${controlPlaneSubnetName}'
output workerSubnetId string = '${vnet.id}/subnets/${workerSubnetName}'
output nsgId string = nsg.id
output natGatewayId string = natGateway.id
output natPublicIp string = natPip.properties.ipAddress
