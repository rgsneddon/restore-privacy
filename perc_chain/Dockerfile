FROM node:20-alpine
WORKDIR /app
COPY package.json ./
COPY src ./src
COPY public ./public
RUN mkdir -p /var/data
ENV PERC_DATA_DIR=/var/data
ENV PERC_BIND_HOST=0.0.0.0
EXPOSE 9478
CMD ["npm", "run", "start:internet"]