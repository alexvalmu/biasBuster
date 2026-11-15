# Despliegue en Google Cloud

```
Firebase Hosting ── /api/** ──▶ Cloud Run: biasbuster-api ──▶ Cloud Tasks ──▶ Cloud Run: biasbuster-worker
                                        │                                              │
                                        └──── Direct VPC egress ──▶ VM e2-micro (Postgres + pgvector) ◀──┘
```

Coste fijo esperado: **≈ 0 €/mes** (capas gratuitas). Lo variable son los tokens de OpenRouter y Tavily.
Todo va en `us-central1`, porque la e2-micro *Always Free* solo existe en `us-central1`, `us-east1` y `us-west1`.

## 0. Requisitos

- `gcloud` y `firebase` CLI con sesión iniciada (`gcloud auth login` y `firebase login`).
- Un proyecto de GCP con facturación activada (hace falta incluso para la capa gratuita).

```bash
export PROJECT_ID=tu-proyecto REGION=us-central1
gcloud config set project $PROJECT_ID
```

## 1. APIs y alerta de presupuesto

```bash
gcloud services enable run.googleapis.com cloudtasks.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com secretmanager.googleapis.com compute.googleapis.com firebase.googleapis.com

# Alerta a los 10 € (ajusta el ID de tu cuenta de facturación)
gcloud billing budgets create --billing-account=XXXXXX-XXXXXX-XXXXXX \
  --display-name=biasbuster --budget-amount=10EUR \
  --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0
```

## 2. Artifact Registry y la imagen de Postgres

```bash
gcloud artifacts repositories create biasbuster --repository-format=docker --location=$REGION

# La VM no tiene IP pública: se descarga la imagen de pgvector desde nuestro registro
docker pull --platform linux/amd64 pgvector/pgvector:pg16
docker tag pgvector/pgvector:pg16 $REGION-docker.pkg.dev/$PROJECT_ID/biasbuster/pgvector:pg16
gcloud auth configure-docker $REGION-docker.pkg.dev
docker push $REGION-docker.pkg.dev/$PROJECT_ID/biasbuster/pgvector:pg16
```

## 3. Red

Usamos la VPC `default`. Activa Private Google Access, para que la VM llegue a Artifact Registry sin IP pública, y abre el 5432 solo dentro de la VPC (Cloud Run sale por la misma subred con Direct VPC egress):

```bash
gcloud compute networks subnets update default --region=$REGION --enable-private-ip-google-access
gcloud compute firewall-rules create allow-postgres-internal --network=default \
  --allow=tcp:5432 --source-ranges=10.128.0.0/9 --target-tags=postgres
# SSH solo a través de IAP
gcloud compute firewall-rules create allow-iap-ssh --network=default \
  --allow=tcp:22 --source-ranges=35.235.240.0/20 --target-tags=postgres
```

## 4. VM de Postgres (e2-micro, Always Free)

```bash
PG_PASSWORD=$(openssl rand -hex 24)

gcloud compute instances create biasbuster-db --zone=$REGION-a \
  --machine-type=e2-micro --no-address --tags=postgres \
  --image-family=cos-stable --image-project=cos-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-standard \
  --scopes=cloud-platform \
  --metadata=pg-password=$PG_PASSWORD,pg-image=$REGION-docker.pkg.dev/$PROJECT_ID/biasbuster/pgvector:pg16 \
  --metadata-from-file=startup-script=infra/db-vm/startup.sh

DB_IP=$(gcloud compute instances describe biasbuster-db --zone=$REGION-a \
  --format='value(networkInterfaces[0].networkIP)')

# Backups: snapshot diario del disco, con 7 días de retención
gcloud compute resource-policies create snapshot-schedule biasbuster-daily --region=$REGION \
  --daily-schedule --start-time=03:00 --max-retention-days=7
gcloud compute disks add-resource-policies biasbuster-db --zone=$REGION-a \
  --resource-policies=biasbuster-daily
```

> **Cuando la e2-micro se quede corta**, crea una instancia de Cloud SQL for PostgreSQL 16 (admite `CREATE EXTENSION vector`), restaura con `pg_dump`/`pg_restore` y actualiza el secreto `database-url`. No hace falta tocar código.

## 5. Secretos

```bash
printf "postgresql+asyncpg://biasbuster:%s@%s:5432/biasbuster" "$PG_PASSWORD" "$DB_IP" \
  | gcloud secrets create database-url --data-file=-
printf "%s" "sk-or-..." | gcloud secrets create openrouter-api-key --data-file=-
printf "%s" "tvly-..."  | gcloud secrets create tavily-api-key --data-file=-
```

## 6. Cuentas de servicio y Cloud Tasks

```bash
for sa in biasbuster-api biasbuster-worker biasbuster-tasks; do
  gcloud iam service-accounts create $sa
done
SA() { echo "$1@$PROJECT_ID.iam.gserviceaccount.com"; }

# Acceso a secretos
for sa in biasbuster-api biasbuster-worker; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:$(SA $sa) --role=roles/secretmanager.secretAccessor
done

# La api encola tareas que se firman como biasbuster-tasks
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$(SA biasbuster-api) --role=roles/cloudtasks.enqueuer
gcloud iam service-accounts add-iam-policy-binding $(SA biasbuster-tasks) \
  --member=serviceAccount:$(SA biasbuster-api) --role=roles/iam.serviceAccountUser

# Cola: como mucho 4 análisis a la vez y 3 intentos, para respetar los rate limits de OpenRouter y Tavily
gcloud tasks queues create analyses --location=$REGION \
  --max-concurrent-dispatches=4 --max-dispatches-per-second=1 \
  --max-attempts=3 --min-backoff=30s --max-backoff=300s
```

## 7. Primer despliegue

```bash
PROJECT_ID=$PROJECT_ID ./infra/scripts/deploy.sh

# Solo Cloud Tasks (con OIDC de biasbuster-tasks) puede invocar el worker
gcloud run services add-iam-policy-binding biasbuster-worker --region=$REGION \
  --member=serviceAccount:$(SA biasbuster-tasks) --role=roles/run.invoker
```

Pon tu ID de proyecto en `.firebaserc`. La web queda en `https://$PROJECT_ID.web.app`.
El worker solo acepta tráfico interno con un token OIDC válido, y eso lo comprueba el propio Cloud Run por IAM.

## 8. Opcional

- **reCAPTCHA v3**: crea las claves y define `RECAPTCHA_SECRET` en la api (como secreto) y `VITE_RECAPTCHA_SITE_KEY` al compilar el frontend.
- **Open Payments**: define `OPEN_PAYMENTS_DATASET_ID` en el worker con el id del dataset *General Payment Data* del año que quieras consultar ([openpaymentsdata.cms.gov](https://openpaymentsdata.cms.gov/)).
- **NCBI**: `NCBI_API_KEY` sube el límite de PubMed de 3 a 10 peticiones por segundo.

## Operación

```bash
# Logs
gcloud run services logs read biasbuster-worker --region=$REGION --limit=100
# Conexión a Postgres a través de IAP
gcloud compute ssh biasbuster-db --zone=$REGION-a --tunnel-through-iap -- \
  docker exec -it postgres psql -U biasbuster
# Coste de los análisis
#   SELECT date_trunc('day', created_at), count(*), sum(cost_usd) FROM analyses GROUP BY 1 ORDER BY 1 DESC;
```
