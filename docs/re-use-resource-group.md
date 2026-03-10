[← Back to *Local Development* guide](LOCAL_DEVELOPMENT.md)

# Reusing an Existing Resource Group

To use an existing Azure Resource Group for your deployment, follow these steps:

---

### 1. Identify the Resource Group

- Visit the [Azure Portal](https://portal.azure.com) and choose the Resource Group you want to reuse.

### 2. Set the Resource Group in your Environment

Before running `azd up`, set the resource group name:

```bash
azd env set AZURE_RESOURCE_GROUP <rg-name>
```
Replace `<rg-name>` with the name of your chosen Resource Group.

### 3. Set the Resource Group location where the specified resource group exists

If you want to specify the location, run:

```bash
azd env set AZURE_LOCATION <location>
```
Replace `<location>` with the desired Azure region.

---

### 4. Continue Deployment

Proceed with the next steps in the [Local Development Guide](LOCAL_DEVELOPMENT.md).
