using './main.bicep'

// ---------------------------------------------------------------------------
// Must match the existing cluster (setup/rt-cluster/parameters.json).
// ---------------------------------------------------------------------------
param location    = 'swedencentral'
param clusterName = 'rt-k8s'
param environment = 'dev'

// ---------------------------------------------------------------------------
// New workers: rt-k8s-worker-6, rt-k8s-worker-7 (existing workers are 0..5).
// ---------------------------------------------------------------------------
param newWorkerCount = 2
param startIndex     = 6
param workerVmSize   = 'Standard_D8ds_v5'
param zones = [
  1
  2
  3
]

// ---------------------------------------------------------------------------
// Same auth as the existing cluster.
//   - SSH key auth: paste your key into sshPublicKey, leave adminPassword a
//     throwaway value (still required to satisfy @secure()/@minLength(12)).
//   - Password auth: leave sshPublicKey empty, set ADMIN_PASSWORD.
// ---------------------------------------------------------------------------
param adminUsername = 'azureuser'
param adminPassword = readEnvironmentVariable('ADMIN_PASSWORD', '')
param sshPublicKey  = readEnvironmentVariable('SSH_PUBLIC_KEY', '')

// ---------------------------------------------------------------------------
// Same shared image gallery as the existing workers.
// ---------------------------------------------------------------------------
param imageSubscriptionId = 'f4ba420a-9799-4a43-bb7d-7fd76761e7a1'
param imageResourceGroup  = 'rg-rt-k8s'
param imageGallery        = 'rtUbuntu'
param imageName           = 'rt-Ubuntu22.04'
param imageVersion        = '1.0.0'
