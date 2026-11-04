#!/bin/sh
set -eu
envsubst '${MARKETPULSE_API_URL}' < /usr/share/nginx/html/config.js.template > /usr/share/nginx/html/config.js
