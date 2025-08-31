# Use a Python 3.11 slim image as the base
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Set the command to run the application
# Use Hypercorn with your app.py
CMD ["hypercorn", "-b", "0.0.0.0:5000", "app:app", "--workers", "2"]
