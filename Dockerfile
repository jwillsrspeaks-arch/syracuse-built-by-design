# Production image for the BUILT BY DESIGN web frontend (static pages + nginx proxy)
FROM nginx:alpine

COPY nginx.prod.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY dashboard.html /usr/share/nginx/html/dashboard.html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
