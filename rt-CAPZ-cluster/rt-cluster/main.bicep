metadata description = 'Self-managed Kubernetes cluster on Azure - VNet + NAT + (optional) internal API LB + VMs'

// ----------------------------------------------------------------------------
// General
// ----------------------------------------------------------------------------
@description('Azure region for every resource.')
param location string = resourceGroup().location

@description('Base name used as a prefix for all resources.')
@minLength(3)
@maxLength(24)
param clusterName string = 'rt-cluster'

@description('Environment tag (dev, test, staging, prod, ...).')
param environment string = 'dev'

@description('Free-form tags applied to every resource (merged with built-ins).')
param extraTags object = {}

// ----------------------------------------------------------------------------
// Sizing
// ----------------------------------------------------------------------------
@description('Number of control plane VMs. An internal load balancer is deployed automatically when this is > 1.')
@minValue(1)
param controlPlaneCount int = 1

@description('Number of worker VMs.')
@minValue(1)
param workerNodeCount int = 2

@description('VM size for control plane nodes.')
param controlPlaneVmSize string = 'Standard_D4ds_v5'

@description('VM size for worker nodes.')
param workerVmSize string = 'Standard_D4ds_v5'

@description('Availability zones to spread VMs across (round-robin). Pass an empty array [] for non-zonal deployment.')
param zones array = [
  1
  2
  3
]

// ----------------------------------------------------------------------------
// Authentication
// ----------------------------------------------------------------------------
@description('Admin username for every VM.')
param adminUsername string = 'azureuser'

@description('Admin password. Used only when sshPublicKey is empty. Must be 12-72 chars with 3 of: lower, upper, digit, symbol.')
@minLength(12)
@secure()
param adminPassword string

@description('SSH public key. When non-empty, password authentication is disabled.')
param sshPublicKey string = ''

// ----------------------------------------------------------------------------
// Image
// ----------------------------------------------------------------------------
@description('Which image to use for the VMs.')
@allowed([
  'custom'
  'ubuntu2404'
])
param imageType string = 'custom'

@description('Subscription ID hosting the custom shared-image gallery (only used when imageType=custom).')
param imageSubscriptionId string = subscription().subscriptionId

@description('Resource group of the custom shared-image gallery (only used when imageType=custom).')
param imageResourceGroup string = ''

@description('Shared-image gallery name (only used when imageType=custom).')
param imageGallery string = ''

@description('Image definition name (only used when imageType=custom).')
param imageName string = ''

@description('Image version, e.g. 1.0.2 or latest (only used when imageType=custom).')
param imageVersion string = 'latest'

// ----------------------------------------------------------------------------
// Networking
// ----------------------------------------------------------------------------
@description('CIDR for the VNet.')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('CIDR for the control plane subnet.')
param controlPlaneSubnetPrefix string = '10.0.1.0/24'

@description('CIDR for the worker subnet.')
param workerSubnetPrefix string = '10.0.2.0/24'

// ----------------------------------------------------------------------------
// Computed values
// ----------------------------------------------------------------------------
var commonTags = union({
  cluster: clusterName
  environment: environment
  managedBy: 'bicep'
}, extraTags)

var customImageId = '/subscriptions/${imageSubscriptionId}/resourceGroups/${imageResourceGroup}/providers/Microsoft.Compute/galleries/${imageGallery}/images/${imageName}/versions/${imageVersion}'

var imageReference = imageType == 'custom' ? {
  id: customImageId
} : {
  publisher: 'Canonical'
  offer: 'ubuntu-24_04-lts'
  sku: 'server'
  version: 'latest'
}

var deployApiLb = controlPlaneCount > 1

// ----------------------------------------------------------------------------
// Modules
// ----------------------------------------------------------------------------
module network 'modules/network.bicep' = {
  name: 'network'
  params: {
    location: location
    clusterName: clusterName
    vnetAddressPrefix: vnetAddressPrefix
    controlPlaneSubnetPrefix: controlPlaneSubnetPrefix
    workerSubnetPrefix: workerSubnetPrefix
    tags: commonTags
  }
}

module apiLoadBalancer 'modules/loadbalancer.bicep' = if (deployApiLb) {
  name: 'api-loadbalancer'
  params: {
    location: location
    clusterName: clusterName
    subnetId: network.outputs.controlPlaneSubnetId
    zones: zones
    tags: commonTags
  }
}

module controlPlane 'modules/vm.bicep' = {
  name: 'control-plane'
  params: {
    location: location
    namePrefix: '${clusterName}-cp'
    count: controlPlaneCount
    vmSize: controlPlaneVmSize
    subnetId: network.outputs.controlPlaneSubnetId
    adminUsername: adminUsername
    adminPassword: adminPassword
    sshPublicKey: sshPublicKey
    imageReference: imageReference
    zones: zones
    loadBalancerBackendPoolIds: deployApiLb ? [ apiLoadBalancer!.outputs.backendPoolId ] : []
    tags: union(commonTags, { role: 'control-plane' })
  }
}

module workers 'modules/vm.bicep' = {
  name: 'workers'
  params: {
    location: location
    namePrefix: '${clusterName}-worker'
    count: workerNodeCount
    vmSize: workerVmSize
    subnetId: network.outputs.workerSubnetId
    adminUsername: adminUsername
    adminPassword: adminPassword
    sshPublicKey: sshPublicKey
    imageReference: imageReference
    zones: zones
    tags: union(commonTags, { role: 'worker' })
  }
}

// ----------------------------------------------------------------------------
// Outputs
// ----------------------------------------------------------------------------
output clusterName string = clusterName
output location string = location
output vnetId string = network.outputs.vnetId
output natEgressIp string = network.outputs.natPublicIp
output controlPlaneVmNames array = controlPlane.outputs.vmNames
output controlPlanePrivateIps array = controlPlane.outputs.privateIps
output workerVmNames array = workers.outputs.vmNames
output workerPrivateIps array = workers.outputs.privateIps
output apiServerEndpoint string = deployApiLb ? apiLoadBalancer!.outputs.apiServerPrivateIp : controlPlane.outputs.privateIps[0]
output apiLoadBalancerDeployed bool = deployApiLb
