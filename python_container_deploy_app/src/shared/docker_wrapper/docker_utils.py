class DockerContainerStartError(Exception):
    def __init__(self, message, container_logs, container_status, container_id):
        super().__init__(message)
        self.container_id = container_id
        self.container_status = container_status
        self.container_logs = container_logs


class InternalDockerError(Exception):
    pass


class InvalidParameterError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


def extract_registry_from_image_name(image_name):
    """
    Extract the Docker registry URL from a given Docker image name.

    Parameters:
        image_name (str): The full name of the Docker image.

    Returns:
        str: The extracted Docker registry URL, or None if not found.
    """
    parts = image_name.split('/')

    # If there's only one part, it means the image is from Docker Hub
    if len(parts) == 1:
        return None  # Default to Docker Hub

    # Check if the first part contains a '.' or a ':', indicating it's likely a registry URL
    if '.' in parts[0] or ':' in parts[0]:
        return parts[0]

    return None  # Default to Docker Hub