# build stage — pinned to the BUILDER's architecture on purpose. This stage
# only emits static files, which are the same bytes whatever CPU runs the
# browser, so there is nothing to gain from running npm under QEMU emulation
# for the arm64 image and several minutes per build to lose.
#
# 22 rather than 20: Vite 7 wants Node ^20.19 || >=22.12, and 20 left support
# in April. Nothing here is served — this stage only produces the dist folder
# the nginx stage below copies.
FROM --platform=$BUILDPLATFORM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# serve stage — static files + reverse proxy to the api container
FROM nginx:1.27-alpine

# A template rather than a finished config: this image's entrypoint runs
# envsubst over /etc/nginx/templates before nginx starts.
#
# The filter is the important part. Without it envsubst would substitute
# every $name in the file, and the config is full of nginx's own — $uri,
# $host, $proxy_add_x_forwarded_for — which would be replaced with nothing
# and break the proxy in ways that only show up under load. Naming the two
# variables explicitly means nothing else is touched.
ENV NGINX_ENVSUBST_FILTER="^(API_UPSTREAM|PORT)$"
# The values this config used to hardcode, so compose installs need set
# neither and behave exactly as before.
ENV API_UPSTREAM=api:8000
ENV PORT=80

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80
