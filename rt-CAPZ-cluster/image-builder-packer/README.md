# Create Custom Image with Image Builder
Here the instructions for buildign the image with image builder:

Follow the quickstart here in case dependencies have not been installed: https://image-builder.sigs.k8s.io/capi/quickstart

```bash
az ad sp create-for-rbac --name "some-name" --role Owner --scopes /subscriptions/sub-id

# add role
az role assignment create \
  --assignee app-id \
  --role Contributor \
  --scope /subscriptions/sub-id

```
Install make and g++ if on linux or wsl
```bash
sudo apt update
# Install make and g++:
sudo apt install make g++
```

```bash
curl -L https://github.com/kubernetes-sigs/image-builder/tarball/main -o image-builder.tgz
mkdir image-builder
tar xzf image-builder.tgz --strip-components 1 -C image-builder
rm image-builder.tgz
cd image-builder/images/capi
```

```bash
export PATH=$PWD/.bin:$PATH
```

and the This for actually installing the Hyper-V modules and publish the image in the Azure Compute Gallery: https://image-builder.sigs.k8s.io/capi/providers/azure

```bash
make deps-azure

```