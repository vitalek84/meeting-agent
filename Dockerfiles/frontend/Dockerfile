# Stage 1: Build the Vite application
FROM node:20-alpine AS builder

# Set the working directory
WORKDIR /app

# Copy package.json and lock files
COPY ./frontend/package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application source code
COPY ./frontend .

# Build the application for production
# This creates the /app/dist folder
RUN npm run build


# Stage 2: Serve the application with Nginx
FROM nginx:stable-alpine

# Copy the built static files from the 'builder' stage to the Nginx html directory
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy the Nginx configuration file
# COPY ./frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80 for the Nginx server
EXPOSE 80

# The Nginx image already has a CMD to start the server, so we don't need to add one.