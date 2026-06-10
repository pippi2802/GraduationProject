using './main.bicep'

// ---------------------------------------------------------------------------
// Cluster identity
// ---------------------------------------------------------------------------
param location     = 'swedencentral'
param clusterName  = 'rt-cluster'
param environment  = 'dev'

// ---------------------------------------------------------------------------
// Sizing
// ---------------------------------------------------------------------------
param controlPlaneCount   = 1
param workerNodeCount     = 2
param controlPlaneVmSize  = 'Standard_D4ds_v5'
param workerVmSize        = 'Standard_D4ds_v5'

// Set to [] for a non-zonal deployment.
param zones = [
  1
  2
  3
]

// ---------------------------------------------------------------------------
// Authentication
//   - For SSH key auth: paste your key into `sshPublicKey` and leave the
//     password as a throwaway value (Azure still requires the param to satisfy
//     the @secure() / @minLength(12) constraints, but it won't be used).
//   - For password auth: leave sshPublicKey empty and set adminPassword via
//     the command line (`--parameters adminPassword=...`) or env var.
// ---------------------------------------------------------------------------
param adminUsername = 'azureuser'
param adminPassword = readEnvironmentVariable('ADMIN_PASSWORD', '')
param sshPublicKey  = readEnvironmentVariable('SSH_PUBLIC_KEY', '')

// ---------------------------------------------------------------------------
// Image
//   imageType = 'ubuntu2404' -> Canonical marketplace image (no other params needed)
//   imageType = 'custom'     -> Shared Image Gallery, fill in the params below.
// ---------------------------------------------------------------------------
param imageType            = 'custom'
param imageSubscriptionId  = 'd06f8f89-f7d3-46b3-b7a8-649244fb54c6'
param imageResourceGroup   = 'rg-rtAKS'
param imageGallery         = 'rtUbuntu'
param imageName            = 'rtUbuntu24.04'
param imageVersion         = '1.0.2'

// ---------------------------------------------------------------------------
// Networking (only override if the defaults conflict with peered networks)
// ---------------------------------------------------------------------------
param vnetAddressPrefix         = '10.0.0.0/16'
param controlPlaneSubnetPrefix  = '10.0.1.0/24'
param workerSubnetPrefix        = '10.0.2.0/24'
