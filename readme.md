# Multi-Tenant Kubeflow Platform on Kubernetes

## 1. Problem Statement

The goal of this project is to design and implement a **multi-tenant Kubeflow service** where multiple customers (tenants) can run machine learning pipelines independently while sharing the same Kubernetes cluster.

Example tenants:

* Customer A → Team RCB
* Customer B → Team RR

### Requirements

* Tenants must work independently
* Isolation must be ensured using namespaces
* All tenants must share the same Kubernetes cluster
* Each tenant should have its own Kubeflow pipeline

---

## 2. Solution Overview

We implemented a **multi-tenant architecture** using:

* Kubernetes as the underlying orchestration platform
* Kubeflow Pipelines for ML workflow execution
* Kubernetes namespaces for tenant isolation
* RBAC roles and resource quotas per tenant for access control and fair usage
* Optional Kind cluster configuration with **OIDC** API server flags for identity integration
* **Group-based RBAC** bindings aligned with OIDC group claims (`rcb-admin`, `rr-readonly`)

Each tenant is assigned a dedicated namespace within a shared Kubernetes cluster, ensuring logical isolation while maintaining efficient resource utilization.

---

## 3. Repository Structure

```
kubernetes-multitenant-assignment/
├── pipelines/                 # Kubeflow pipeline definitions (Python + compiled YAML)
│   ├── rcb_pipeline.py
│   ├── rcb_pipeline.yaml
│   ├── rr_pipeline.py
│   └── rr_pipeline.yaml
├── setup/                     # Cluster and namespace bootstrap
│   ├── kind-config.yaml       # Kind cluster (control-plane + worker, Kubernetes v1.29.4)
│   ├── oidc-kind-config.yaml  # Same cluster shape + OIDC issuer flags on the API server
│   └── namespaces.yaml        # Tenant namespaces: rcb, rr
├── security/                  # Per-tenant RBAC and resource quotas
│   ├── rcb-role.yaml
│   ├── rcb-rolebinding.yaml
│   ├── rr-role.yaml
│   ├── rr-rolebinding.yaml
│   ├── resource-quota-rcb.yaml
│   └── resource-quota-rr.yaml
├── requirements.txt           # Python deps (kfp 2.16.0, kubernetes, etc.)
├── .gitignore
└── readme.md
```

---

## 4. Architecture

### High-Level Architecture

```
Kubernetes Cluster (Shared)
│
├── Namespace: rcb
│   ├── RCB ML Pipeline (iris / LogisticRegression)
│   ├── RBAC (OIDC group rcb-admin → rcb-role)
│   ├── ResourceQuota (tenant-quota)
│   └── Pods (Pipeline Execution)
│
├── Namespace: rr
│   ├── RR ML Pipeline (wine / DecisionTreeClassifier)
│   ├── RBAC (OIDC group rr-readonly → rr-role)
│   ├── ResourceQuota (tenant-quota)
│   └── Pods (Pipeline Execution)
│
└── Namespace: kubeflow
    ├── Kubeflow Pipelines UI
    ├── Workflow Controller
    └── Metadata & Storage Services
```

---

## 5. Key Components

### 5.1 Kubernetes

* Provides container orchestration
* Manages pods, scheduling, and resource allocation
* Enables namespace-based isolation

### 5.2 Kubeflow Pipelines

* Used to define and execute ML workflows
* Converts Python-based pipeline definitions into Kubernetes workloads
* Executes each pipeline step as a Kubernetes pod

### 5.3 Namespaces (Core of Multi-Tenancy)

* `rcb` → Customer A (Team RCB)
* `rr` → Customer B (Team RR)

Namespaces provide logical isolation, separate resource visibility, and independent execution environments.

### 5.4 RBAC

Per-tenant `Role` and `RoleBinding` manifests in `security/` grant namespace-scoped access. Bindings use **OIDC groups** (from the API server `oidc-groups-claim`) rather than static Kubernetes users:

| Tenant | OIDC group    | Role       | Access level |
|--------|---------------|------------|--------------|
| RCB    | `rcb-admin`   | `rcb-role` | Full workload management in `rcb` |
| RR     | `rr-readonly` | `rr-role`  | Read-only on `pods` and `services` in `rr` |

**RCB (`rcb-role`)** — `pods`, `services`, `configmaps`, `secrets`: `get`, `list`, `watch`, `create`, `update`, `delete`.

**RR (`rr-role`)** — `pods`, `services`: `get`, `list`, `watch` only.

This models two tenants with different privilege levels on the same shared cluster.

### 5.5 OIDC-ready Kind cluster

`setup/oidc-kind-config.yaml` extends the base Kind config with API server OIDC flags:

| Setting | Value |
|---------|--------|
| `oidc-issuer-url` | `http://host.docker.internal:8081/realms/kubeflow-multitenant` |
| `oidc-client-id` | `kubeflow-client` |
| `oidc-username-claim` | `preferred_username` |
| `oidc-groups-claim` | `groups` |

Use this config when an external IdP (e.g. Keycloak) issues tokens whose `groups` claim matches `rcb-admin` or `rr-readonly`. For local testing without OIDC, use `setup/kind-config.yaml` instead.

**Obtain an access token** (Keycloak resource-owner password grant; replace placeholders with your realm client and user values—do not commit secrets):

```bash
curl -X POST "http://localhost:8081/realms/kubeflow-multitenant/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=kubeflow-client" \
  -d "client_secret=<your-client-secret>" \
  -d "username=<your-username>" \
  -d "password=<your-password>" \
  -d "grant_type=password"
```

The response includes an `access_token` you can pass to `kubectl` or other clients configured for OIDC authentication.

### 5.6 Resource Quotas

Each tenant namespace has a `ResourceQuota` (`tenant-quota`) limiting:

| Resource           | Limit   |
|--------------------|---------|
| `requests.cpu`     | 2       |
| `requests.memory`  | 2Gi     |
| `limits.cpu`       | 4       |
| `limits.memory`    | 4Gi     |

---

## 6. Pipeline Execution Flow

```
User → Kubeflow UI → Pipeline Submission
      ↓
Pipeline Compiled (Python → YAML)
      ↓
Workflow Created in Kubernetes
      ↓
Pods Scheduled in Cluster
      ↓
Execution Completed
      ↓
Logs & Results Available
```

---

## 7. Getting Started

### Prerequisites

* [Docker](https://docs.docker.com/get-docker/)
* [Kind](https://kind.sigs.k8s.io/)
* [kubectl](https://kubernetes.io/docs/tasks/tools/)
* Python 3.x

### 1. Create the cluster

**Without OIDC** (simple local cluster):

```bash
kind create cluster --config setup/kind-config.yaml
```

**With OIDC** (API server accepts tokens from your IdP; ensure the issuer is reachable from the Kind node):

```bash
kind create cluster --config setup/oidc-kind-config.yaml
```

### 2. Apply tenant namespaces

```bash
kubectl apply -f setup/namespaces.yaml
```

### 3. Apply security policies

```bash
kubectl apply -f security/
```

### 4. Install Python dependencies and compile pipelines

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python pipelines/rcb_pipeline.py
python pipelines/rr_pipeline.py
```

This regenerates `pipelines/rcb_pipeline.yaml` and `pipelines/rr_pipeline.yaml` from the Python definitions.

### 5. Deploy Kubeflow Pipelines and run workloads

Install Kubeflow Pipelines (standalone) on the cluster, port-forward to the UI, upload the compiled YAML artifacts, and submit runs per tenant namespace.

---

## 8. Pipelines

| Pipeline     | Source                      | Compiled artifact               | Workload |
|--------------|-----------------------------|---------------------------------|----------|
| RCB pipeline | `pipelines/rcb_pipeline.py` | `pipelines/rcb_pipeline.yaml`   | Iris dataset, `LogisticRegression` (pandas + scikit-learn) |
| RR pipeline  | `pipelines/rr_pipeline.py`  | `pipelines/rr_pipeline.yaml`    | Wine dataset, `DecisionTreeClassifier` (scikit-learn) |

Each pipeline is a KFP v2 workflow with a single `@dsl.component` training step. Component images install runtime deps via `packages_to_install` (`pandas`/`scikit-learn` for RCB; `scikit-learn` for RR). Recompile after editing the `.py` files:

```bash
python pipelines/rcb_pipeline.py
python pipelines/rr_pipeline.py
```

---

## 9. Multi-Tenancy Strategy

Multi-tenancy is achieved using **Kubernetes namespaces**, reinforced with **RBAC** and **resource quotas**.

### Isolation mechanism

* Each tenant operates within its own namespace
* Resources (pods, workloads) are scoped to namespaces
* RBAC restricts API access to namespace-bound OIDC groups
* Resource quotas cap CPU and memory per tenant
* Optional OIDC on the API server maps identity provider groups to tenant roles

### Benefits

* Cost-efficient (shared cluster)
* Scalable
* Access control and usage limits beyond namespace labels alone

---

## 10. Isolation Demonstration

Verify isolation by listing pods per namespace:

```bash
kubectl get pods -n rcb
kubectl get pods -n rr
```

Check quotas and RBAC:

```bash
kubectl get resourcequota -n rcb
kubectl get resourcequota -n rr
kubectl get role,rolebinding -n rcb
kubectl get role,rolebinding -n rr
```

---

## 11. Trade-offs

### Advantages

* Efficient resource utilization on a shared cluster
* Easy to add tenants (namespace + security manifests + pipeline)
* RBAC and quotas improve fairness and access boundaries

### Limitations

* Namespace isolation is logical, not a hard security boundary
* Potential “noisy neighbor” issues remain under heavy load
* OIDC requires a running IdP and matching group claims; `oidc-kind-config.yaml` only configures the API server—you still need token issuance and `kubectl` OIDC login in production

---

## 12. Future Enhancements

### KServe integration

* Deploy trained models as APIs
* Enable real-time inference

### GPU support

* Enable GPU-based workloads using Kubernetes device plugins
* Allow pipelines to request GPU resources

### Stronger tenancy

* NetworkPolicies for traffic isolation between namespaces
* LimitRanges and PodSecurity standards per tenant
* Align RR role with write access if that tenant needs to submit pipelines (currently read-only)

---

## 13. Conclusion

This project demonstrates a **multi-tenant Kubeflow platform** on Kubernetes where multiple customers can share infrastructure, run independent ML pipelines, and operate in isolated namespaces with group-based RBAC, resource quotas, and optional OIDC integration. The repository provides reproducible setup, security, and pipeline artifacts for two example tenants (RCB and RR).
