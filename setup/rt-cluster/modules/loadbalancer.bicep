metadata description = 'Internal Standard Load Balancer for the Kubernetes API server (port 6443)'

@description('Azure region.')
param location string

@description('Base name used to derive resource names.')
param clusterName string

@description('Subnet ID where the internal LB frontend lives (control plane subnet).')
param subnetId string

@description('Availability zones for the frontend IP. Empty array => no zone (regional).')
param zones array = []

@description('Tags applied to every resource.')
param tags object = {}

var lbName = '${clusterName}-api-lb'
var frontendName = 'api-frontend'
var backendPoolName = 'api-backend'
var probeName = 'api-probe'
var ruleName = 'api-rule'

var zoneStrings = map(zones, z => string(z))

resource lb 'Microsoft.Network/loadBalancers@2023-11-01' = {
  name: lbName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Regional'
  }
  properties: {
    frontendIPConfigurations: [
      {
        name: frontendName
        zones: empty(zoneStrings) ? null : zoneStrings
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: {
            id: subnetId
          }
        }
      }
    ]
    backendAddressPools: [
      {
        name: backendPoolName
      }
    ]
    probes: [
      {
        name: probeName
        properties: {
          protocol: 'Tcp'
          port: 6443
          intervalInSeconds: 15
          numberOfProbes: 2
        }
      }
    ]
    loadBalancingRules: [
      {
        name: ruleName
        properties: {
          frontendIPConfiguration: {
            id: resourceId('Microsoft.Network/loadBalancers/frontendIPConfigurations', lbName, frontendName)
          }
          backendAddressPool: {
            id: resourceId('Microsoft.Network/loadBalancers/backendAddressPools', lbName, backendPoolName)
          }
          probe: {
            id: resourceId('Microsoft.Network/loadBalancers/probes', lbName, probeName)
          }
          protocol: 'Tcp'
          frontendPort: 6443
          backendPort: 6443
          idleTimeoutInMinutes: 4
          enableFloatingIP: false
          loadDistribution: 'Default'
        }
      }
    ]
  }
}

output loadBalancerId string = lb.id
output backendPoolId string = '${lb.id}/backendAddressPools/${backendPoolName}'
output apiServerPrivateIp string = lb.properties.frontendIPConfigurations[0].properties.privateIPAddress
