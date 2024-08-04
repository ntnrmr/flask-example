#!/bin/bash

set -euo pipefail

app_name="example"
region="us-central1"
project_id=$(gcloud config get-value project)
tag=$(git rev-parse --short HEAD)
image_name="gcr.io/$project_id/$app_name:$tag"
blue_green_traffic_delay=60

gcloud builds submit --tag "$image_name"

gcloud run deploy $app_name \
  --image $image_name \
  --region $region \
  --no-traffic

current_rev=$(gcloud run services describe $app_name --region $region --format="value(status.traffic[0].revisionName)")
new_rev=$(gcloud run revisions list --service $app_name --region $region --sort-by="~createTime" --limit=1 --format="value(METADATA.name)")

echo "Current revision: $current_rev"
echo "New revision: $new_rev"

declare -a traffic_splits=("1" "10" "50" "100")

for percent in "${traffic_splits[@]}"; do
  echo "Shifting $percent% traffic to new revision..."
  gcloud run services update-traffic $app_name \
    --region $region \
    --to-revisions ${new_rev}=${percent},${current_rev}=$((100 - percent))

  if [ $percent -lt 100 ]; then
    echo "Waiting for $blue_green_traffic_delay seconds before next shift..."
    sleep $blue_green_traffic_delay
  fi
done

echo "Deployment complete. 100% traffic is now routed to the new revision: $new_rev"
