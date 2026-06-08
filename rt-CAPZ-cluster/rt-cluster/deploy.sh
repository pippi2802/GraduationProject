#!/bin/bash
# Deployment script for Kubernetes cluster on Azure using Bicep

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="dev"
LOCATION="swedencentral"
CLUSTER_NAME="capi-dev"
CONTROL_PLANE_COUNT=1
WORKER_NODE_COUNT=2
ACTION="deploy"
VALIDATE_ONLY=false

# Function to print colored output
print_header() {
    echo -e "${BLUE}===================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

OPTIONS:
    -e, --environment ENV              Environment name (dev/staging/prod) [default: dev]
    -l, --location LOCATION            Azure region [default: swedencentral]
    -c, --cluster-name NAME            Cluster name [default: capi-dev]
    -p, --control-plane-count NUM      Number of control plane nodes [default: 1]
    -w, --worker-node-count NUM        Number of worker nodes [default: 2]
    -s, --subscription SUB_ID          Azure subscription ID
    -r, --resource-group RG            Resource group name
    --validate                         Validate template without deploying
    --what-if                          Show what would be created
    --delete                           Delete the deployment
    -h, --help                         Show this help message

EXAMPLES:
    # Deploy with defaults
    $0

    # Deploy 3 control planes and 5 workers
    $0 -p 3 -w 5

    # Validate template
    $0 --validate

    # Delete deployment
    $0 --delete

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -l|--location)
            LOCATION="$2"
            shift 2
            ;;
        -c|--cluster-name)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        -p|--control-plane-count)
            CONTROL_PLANE_COUNT="$2"
            shift 2
            ;;
        -w|--worker-node-count)
            WORKER_NODE_COUNT="$2"
            shift 2
            ;;
        -s|--subscription)
            SUBSCRIPTION_ID="$2"
            shift 2
            ;;
        -r|--resource-group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        --validate)
            VALIDATE_ONLY=true
            shift
            ;;
        --what-if)
            ACTION="what-if"
            shift
            ;;
        --delete)
            ACTION="delete"
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Set default resource group if not provided
RESOURCE_GROUP="${RESOURCE_GROUP:-capi-${ENVIRONMENT}}"

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check Azure CLI
    if ! command -v az &> /dev/null; then
        print_error "Azure CLI is not installed"
        echo "Install from: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    fi
    print_success "Azure CLI installed"

    # Check Bicep
    if ! az bicep version &> /dev/null; then
        print_warning "Bicep CLI not found, installing..."
        az bicep install
    fi
    print_success "Bicep CLI available"

    # Check if logged in
    if ! az account show &> /dev/null; then
        print_warning "Not logged in to Azure"
        read -p "Do you want to login now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            az login --use-device-code
        else
            print_error "Cannot proceed without Azure authentication"
            exit 1
        fi
    fi
    print_success "Authenticated to Azure"
}

# Display configuration
display_configuration() {
    print_header "Deployment Configuration"
    echo "Environment:            $ENVIRONMENT"
    echo "Location:               $LOCATION"
    echo "Cluster Name:           $CLUSTER_NAME"
    echo "Resource Group:         $RESOURCE_GROUP"
    echo "Control Plane Nodes:    $CONTROL_PLANE_COUNT"
    echo "Worker Nodes:           $WORKER_NODE_COUNT"
    if [ -n "$SUBSCRIPTION_ID" ]; then
        echo "Subscription ID:        $SUBSCRIPTION_ID"
    fi
    echo ""
}

# Prompt for service principal
get_service_principal_details() {
    print_header "Service Principal Configuration"
    
    echo "To enable cluster access to Azure resources, provide service principal details:"
    echo ""
    
    read -p "Tenant ID (e.g., cb5b3c56-8331-4862-8e2c-369b8684fdc0): " -e TENANT_ID
    read -p "Client ID / Application ID: " -e CLIENT_ID
    read -sp "Client Secret / Password (will not be echoed): " CLIENT_SECRET
    echo ""
    
    if [ -z "$TENANT_ID" ] || [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
        print_error "Service principal details are required"
        exit 1
    fi
    
    print_success "Service principal details received"
}

# Set Azure subscription
set_subscription() {
    if [ -z "$SUBSCRIPTION_ID" ]; then
        print_header "Selecting Subscription"
        
        # List subscriptions
        print_info "Available subscriptions:"
        az account list --output table --query "[].{Name:name, ID:id, Default:isDefault}"
        echo ""
        
        read -p "Enter subscription ID or name: " SUBSCRIPTION_ID
    fi
    
    az account set --subscription "$SUBSCRIPTION_ID"
    print_success "Subscription set to $SUBSCRIPTION_ID"
}

# Create resource group
create_resource_group() {
    print_header "Creating Resource Group"
    
    if az group exists --name "$RESOURCE_GROUP" | grep -q true; then
        print_warning "Resource group '$RESOURCE_GROUP' already exists"
    else
        print_info "Creating resource group '$RESOURCE_GROUP' in $LOCATION..."
        az group create \
            --name "$RESOURCE_GROUP" \
            --location "$LOCATION"
        print_success "Resource group created"
    fi
}

# Validate deployment
validate_deployment() {
    print_header "Validating Template"
    
    print_info "Validating Bicep template..."
    az deployment group validate \
        --resource-group "$RESOURCE_GROUP" \
        --template-file main.bicep \
        --parameters parameters.biceparam \
        --parameters \
            environment="$ENVIRONMENT" \
            location="$LOCATION" \
            clusterName="$CLUSTER_NAME" \
            resourceGroupName="$RESOURCE_GROUP" \
            controlPlaneCount="$CONTROL_PLANE_COUNT" \
            workerNodeCount="$WORKER_NODE_COUNT" \
            tenantId="$TENANT_ID" \
            servicePrincipalClientId="$CLIENT_ID" \
            servicePrincipalClientSecret="$CLIENT_SECRET" \
        --output table
    
    print_success "Template validation passed"
}

# What-if deployment
what_if_deployment() {
    print_header "What-If Analysis"
    
    print_info "Showing what would be created..."
    az deployment group what-if \
        --resource-group "$RESOURCE_GROUP" \
        --template-file main.bicep \
        --parameters parameters.biceparam \
        --parameters \
            environment="$ENVIRONMENT" \
            location="$LOCATION" \
            clusterName="$CLUSTER_NAME" \
            resourceGroupName="$RESOURCE_GROUP" \
            controlPlaneCount="$CONTROL_PLANE_COUNT" \
            workerNodeCount="$WORKER_NODE_COUNT" \
            tenantId="$TENANT_ID" \
            servicePrincipalClientId="$CLIENT_ID" \
            servicePrincipalClientSecret="$CLIENT_SECRET"
}

# Deploy infrastructure
deploy_infrastructure() {
    print_header "Deploying Infrastructure"
    
    print_info "Starting Bicep deployment..."
    print_info "This may take 10-30 minutes. Please wait..."
    echo ""
    
    DEPLOYMENT_NAME="deployment-$(date +%Y%m%d-%H%M%S)"
    
    az deployment group create \
        --name "$DEPLOYMENT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --template-file main.bicep \
        --parameters parameters.biceparam \
        --parameters \
            environment="$ENVIRONMENT" \
            location="$LOCATION" \
            clusterName="$CLUSTER_NAME" \
            resourceGroupName="$RESOURCE_GROUP" \
            controlPlaneCount="$CONTROL_PLANE_COUNT" \
            workerNodeCount="$WORKER_NODE_COUNT" \
            tenantId="$TENANT_ID" \
            servicePrincipalClientId="$CLIENT_ID" \
            servicePrincipalClientSecret="$CLIENT_SECRET"
    
    DEPLOY_STATUS=$?
    
    echo ""
    if [ $DEPLOY_STATUS -eq 0 ]; then
        print_success "Deployment completed successfully!"
    else
        print_error "Deployment failed with exit code $DEPLOY_STATUS"
        exit 1
    fi
}

# Delete deployment
delete_deployment() {
    print_header "Deleting Deployment"
    
    print_warning "This will delete all resources in the resource group '$RESOURCE_GROUP'"
    read -p "Are you sure? (yes/no): " CONFIRM
    
    if [ "$CONFIRM" != "yes" ]; then
        print_info "Deletion cancelled"
        exit 0
    fi
    
    print_info "Deleting resource group..."
    az group delete \
        --name "$RESOURCE_GROUP" \
        --yes \
        --no-wait
    
    print_success "Deletion initiated (this may take a few minutes to complete in background)"
}

# Display next steps
show_next_steps() {
    print_header "Next Steps"
    
    echo "1. Wait for all VMs to start and complete initialization"
    echo ""
    echo "2. Get VM information:"
    echo "   az vm list --resource-group \"$RESOURCE_GROUP\" -o table"
    echo ""
    echo "3. Get VM IP addresses:"
    echo "   az vm list-ip-addresses --resource-group \"$RESOURCE_GROUP\" -o table"
    echo ""
    echo "4. SSH into control plane:"
    echo "   ssh -i ~/.ssh/azure_rsa azureuser@<CONTROL_PLANE_IP>"
    echo ""
    echo "5. Initialize Kubernetes on control plane:"
    echo "   sudo kubeadm init --pod-network-cidr=192.168.0.0/16"
    echo ""
    echo "6. Setup kubeconfig:"
    echo "   mkdir -p \$HOME/.kube"
    echo "   sudo cp /etc/kubernetes/admin.conf \$HOME/.kube/config"
    echo "   sudo chown \$(id -u):\$(id -g) \$HOME/.kube/config"
    echo ""
    echo "7. Install CNI plugin (e.g., Calico):"
    echo "   kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/tigera-operator.yaml"
    echo ""
    echo "8. Join worker nodes to cluster with the token from control plane"
    echo ""
    echo "For more details, see README.md"
    echo ""
}

# Main execution
main() {
    print_header "Kubernetes Cluster Deployment on Azure using Bicep"
    
    # Change to script directory
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    cd "$SCRIPT_DIR"
    
    # Check prerequisites
    check_prerequisites
    
    # Display configuration
    display_configuration
    
    # Confirm before proceeding
    if [ "$ACTION" != "delete" ]; then
        read -p "Proceed with deployment? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Cancelled by user"
            exit 0
        fi
    fi
    
    # Set subscription
    set_subscription
    
    # Get service principal details if not delete or what-if
    if [ "$ACTION" != "delete" ] && [ "$ACTION" != "what-if" ]; then
        get_service_principal_details
    fi
    
    # Create resource group
    create_resource_group
    
    # Execute action
    case $ACTION in
        deploy)
            validate_deployment
            read -p "Validation passed. Deploy now? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                deploy_infrastructure
                show_next_steps
            else
                print_info "Deployment cancelled"
            fi
            ;;
        what-if)
            what_if_deployment
            ;;
        delete)
            delete_deployment
            ;;
        *)
            print_error "Unknown action: $ACTION"
            exit 1
            ;;
    esac
    
    print_success "Script completed"
}

# Run main function
main "$@"
