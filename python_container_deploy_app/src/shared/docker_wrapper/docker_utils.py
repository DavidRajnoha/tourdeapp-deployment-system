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
    Extracts the Docker registry URL from a given Docker image name. This function identifies whether the image name
    includes a registry URL based on specific patterns within the name. A registry URL is recognized if the first segment
    of the image name contains either a dot (indicating a domain) or a colon (indicating a port), which are typical
    characteristics of a registry URL. If no such pattern is found, it is assumed that the image is hosted on Docker Hub,
    and the function returns None.

    :param image_name: str. The full name of the Docker image which may include a registry URL, repository name, and optionally a tag.
    :return: str or None. The extracted Docker registry URL if present; otherwise, None, indicating the image is from Docker Hub.
    """
    parts = image_name.split('/')

    # If there's only one part, it means the image is from Docker Hub
    if len(parts) == 1:
        return None  # Default to Docker Hub

    # Check if the first part contains a '.' or a ':', indicating it's likely a registry URL
    if '.' in parts[0] or ':' in parts[0]:
        return parts[0]

    return None  # Default to Docker Hub