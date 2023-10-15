# Use an official Python runtime as a parent image
FROM python:3.11-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Setup entry point
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Install any needed packages specified in requirements.txt
RUN pip install pipenv \
    && pipenv install --system --deploy

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Run entrypoint.sh when the container launches
CMD ["/entrypoint.sh"]