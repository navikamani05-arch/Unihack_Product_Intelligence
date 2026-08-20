# Deployment source notes

## Render Web Services
URL: https://render.com/docs/web-services

The official Render documentation states that a web service can deploy from a Git repository or Docker image, receives a public `onrender.com` subdomain, supports environment variables, health-check paths, persistent disks, and managed TLS. It requires the service to bind to `0.0.0.0` and recommends using the `PORT` environment variable. Render terminates inbound SSL and redirects HTTP to HTTPS.

## Render Persistent Disks
URL: https://render.com/docs/disks

The official Render documentation states that service filesystems are ephemeral by default. A persistent disk preserves filesystem changes under its mount path across deploys and restarts. For Docker services, `/app/storage` is an example mount path. Persistent disks are available to paid services, are single-instance, and prevent zero-downtime deploys.

## Railway Volumes
URL: https://docs.railway.com/volumes

The official Railway documentation states that volumes persist service data, must be mounted at the path used by the application, and that relative `./data` writes in an `/app` container should use a volume mounted at `/app/data`. Volumes are mounted at runtime, not build time.

## Fly.io FastAPI
URL: https://fly.io/docs/python/frameworks/fastapi/

The official Fly.io documentation provides a Docker-based FastAPI deployment flow, public `fly.dev` HTTPS URLs, and `fly deploy` workflow. It supports FastAPI services packaged as deployable images.

## Project-specific implications

The backend Dockerfile binds Uvicorn to `0.0.0.0` and uses `${PORT}`. The application stores its SQLite database and uploaded files on the backend filesystem (`./data` and `data/uploads`). Therefore a deployed demo needs a durable mounted volume at `/app/data` or a separately configured durable database/object-storage strategy. A frontend-only Vercel deployment cannot safely provide this backend persistence.
