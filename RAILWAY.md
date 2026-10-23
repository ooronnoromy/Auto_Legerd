# Deploy AutoLedger to Railway

This deployment uses a Docker web service, Railway PostgreSQL, and one persistent
volume for vehicle, receipt, and pump images.

## 1. Upload the source

Create a private GitHub repository and upload this project's source, including
`Dockerfile`, `railway.json`, `gunicorn.conf.py`, and the `deploy` folder.
Do not upload `.env`, `.venv`, `.run`, `db.sqlite3`, `media`, or `staticfiles`.
The ignore files exclude them when using Git and Docker.

In Railway, choose **New Project -> Deploy from GitHub repo**, select the repo,
and name the web service `autoledger`. Its first deploy may fail until the next
steps are configured.

## 2. Add PostgreSQL and a media volume

In the same Railway project and environment:

1. Add a PostgreSQL service. These examples assume its name is `Postgres`.
2. Attach a volume to the **autoledger web service**, mounted at `/data`.
   This is separate from PostgreSQL's own volume.
3. Keep the web service at **one replica** when using this volume.

Uploads live in `/data/media`. Railway files outside a volume do not survive
redeploys. Without a volume, the app starts and logs a temporary-storage warning;
attach the volume before saving photos you want to keep.

## 3. Set the web service variables

Set these in **autoledger -> Variables**, not in your local `.env`:

| Variable | Value |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | `config.production` |
| `DJANGO_DEBUG` | `false` |
| `SECRET_KEY` | A new random secret generated below |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `MEDIA_ROOT` | `/data/media` |
| `WEB_CONCURRENCY` | `2` |

For mobile car/expense notifications, also set `PUSH_VAPID_PUBLIC_KEY`,
`PUSH_VAPID_PRIVATE_KEY`, and `PUSH_VAPID_SUBJECT` using the stable values in
your ignored `.run/push-keys.env` file. See [mobile notification setup](PUSH_NOTIFICATIONS.md).
The default Docker start command runs the push worker alongside the web app.

Use Railway's reference-variable picker for `DATABASE_URL` if your database
service has another name. Use its internal URL from this same environment;
PostgreSQL does not need public networking. `DATABASE_URL` overrides local
SQLite and `POSTGRES_*` settings.

Generate a new production secret locally:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
```

Copy it to Railway's `SECRET_KEY` and keep it stable between deployments.
Do not reuse your development login password as a secret.

Railway supplies `PORT`; Gunicorn listens on `0.0.0.0:$PORT`. Leave the custom
start-command field empty to use the Dockerfile command.

## 4. Deploy and generate an HTTPS domain

Deploy the pending changes. `railway.json` configures the Docker build, automatic
database migrations before deployment, and `/healthz/` readiness checks.
Static files are collected and compressed during the image build.

Open **Settings -> Networking -> Public Networking -> Generate Domain**.
Railway supplies `RAILWAY_PUBLIC_DOMAIN`, which the app automatically adds to
allowed hosts and trusted HTTPS origins. Redeploy after domain generation if it
was not present when the service started.

For a custom domain, also set:

```dotenv
ALLOWED_HOSTS=your-domain.example
CSRF_TRUSTED_ORIGINS=https://your-domain.example
```

Use comma-separated values for multiple custom domains. The generated Railway
domain and health-check hostname are added automatically.

## 5. Create the production administrator

The Railway database starts empty. Local users, passwords, records, and images
are **not transferred automatically**, and the local admin password is not
bundled in the image.

Open a deployed-service shell using Railway's **Copy SSH Command** action,
or `railway ssh` after linking the CLI to the web service, then run:

```sh
python manage.py createsuperuser
```

Enter your phone number as the username and choose a new password. Then open
`https://YOUR-RAILWAY-DOMAIN/admin/` or `/login/`.

To reset a password, run in that same deployed-service shell:

```sh
python manage.py changepassword YOUR_PHONE_NUMBER
```

Running this command locally only changes your local account. Moving existing
local data and photos requires a separate data migration after backing up both
databases; deploying source does not transfer application data.

## 6. Verify and maintain

1. `/healthz/` should return HTTP 200 and `{"status":"ok"}`.
2. Sign in, add a vehicle, and create an expense with a photo.
3. Open reports and download CSV.
4. Sign out: photo URLs should require login.
5. Redeploy and confirm records and photos remain available.

Run these in the deployed-service shell:

```sh
python manage.py check --deploy --fail-level WARNING
python manage.py showmigrations
```

Photos are served through authenticated Django views; owners and staff have
access. WhiteNoise serves only public static assets. Enable backups for both
the PostgreSQL database and the media volume. Keep one web replica with this
disk-based upload configuration.

## Troubleshooting

If the crash logs show `ImproperlyConfigured: Set SECRET_KEY`, open the **web
service -> Variables**, add or replace `SECRET_KEY` with a generated value of at
least 50 characters, and deploy the variable change. Set it on the web service,
not just PostgreSQL. Editing your local `.env` does not change Railway variables.
If `.run/railway-secret.txt` was generated during troubleshooting, copy its
contents as the variable value; this file is intentionally excluded from Git,
Docker, and the deployment ZIP. Keep this key stable after the site starts.

| Symptom | Check |
| --- | --- |
| Secret-key startup error | Use a new `SECRET_KEY` of at least 50 characters. |
| Database startup error | Add PostgreSQL and its `DATABASE_URL` reference. |
| Temporary-storage warning | Attach `/data`; set `MEDIA_ROOT=/data/media` to preserve photos. |
| HTTP 400 / invalid host | Generate the domain and redeploy; set custom allowed hosts. |
| CSRF login error | Use HTTPS and add custom domains to trusted origins. |
| Health check fails | Check migration logs and database connectivity. |
| Cannot sign in | Create a superuser in the deployed-service shell. |

References: [Django on Railway](https://docs.railway.com/guides/django),
[configuration as code](https://docs.railway.com/config-as-code/reference),
[health checks](https://docs.railway.com/deployments/healthchecks),
[volumes](https://docs.railway.com/volumes),
[Railway SSH](https://docs.railway.com/cli/ssh).
