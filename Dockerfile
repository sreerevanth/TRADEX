# Use an official lightweight Python image
FROM python:3.11-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create an unprivileged user 'streamlit'
RUN useradd -m -u 1000 streamlit

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (if any are needed by python packages)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Copy the requirements file to the working directory
COPY requirements.txt .

# Install Python dependencies globally
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code and set ownership to 'streamlit'
COPY --chown=streamlit:streamlit . .

# Switch to the non-root user
USER streamlit

# Run the application
CMD ["python", "app.py"]
