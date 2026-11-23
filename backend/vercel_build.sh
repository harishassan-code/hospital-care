#!/bin/sh
# The API's build step on Vercel (B14), named in pyproject.toml ([tool.vercel.scripts] build). Vercel runs it after
# installing the dependencies and before it collects the static files. A failure stops the deploy, with the reason
# in the build log.
set -eu

# A setting that would make staging unsafe (DEBUG on, a weak key, no HTTPS) fails the build here (B13, #58).
python manage.py check --deploy --fail-level WARNING

# Only production deploys change the database. A preview deploy (one per pull request) uses the same database,
# so it mustn't apply a pull request's migrations to it. (Vercel sets VERCEL_ENV; unset counts as production.)
if [ "${VERCEL_ENV:-production}" != "production" ]; then
  echo "A $VERCEL_ENV deploy: the database is left as it is (production deploys migrate it)."
  exit 0
fi

# Migrations over a direct connection when Neon offers one; the pooled one is for the app's short requests.
DATABASE_URL="${DATABASE_URL_UNPOOLED:-${DATABASE_URL:-}}"
if [ -z "$DATABASE_URL" ]; then
  echo "DATABASE_URL is not set: connect a Postgres database to the project (Storage tab), then redeploy." >&2
  exit 1
fi
export DATABASE_URL

python manage.py migrate --noinput
python manage.py createcachetable
# Demo hospitals and one login per role; only fills empty tables, so it's safe on every deploy.
python manage.py seed_demo
