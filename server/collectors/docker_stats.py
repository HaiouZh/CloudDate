"""
CloudDate — Docker Collector
Collects Docker container status information.
Inspired by cAdvisor's container monitoring but simplified to basic status only.
Uses Docker SDK (docker-py) via the docker.sock socket.
"""

import logging

logger = logging.getLogger("clouddate.docker")

# Lazy-load docker client to avoid import errors when docker is not installed
_docker_client = None
_docker_available = None


def _get_docker_client():
    """Lazy-initialize Docker client. Returns None if Docker is not available."""
    global _docker_client, _docker_available

    if _docker_available is False:
        return None

    if _docker_client is not None:
        return _docker_client

    try:
        import docker
        _docker_client = docker.from_env()
        _docker_client.ping()
        _docker_available = True
        logger.info("Docker connection established")
        return _docker_client
    except Exception as e:
        _docker_available = False
        logger.warning(f"Docker not available: {e}")
        return None


def collect_docker() -> list[dict]:
    """
    Collect Docker container information.
    Returns a list of container dicts with name, image, status, uptime.

    Inspired by cAdvisor's container stats collection but limited to
    basic status information for lightweight operation.
    """
    client = _get_docker_client()
    if client is None:
        return []

    containers = []

    try:
        for container in client.containers.list(all=True):
            info = {
                "id": container.short_id,
                "name": container.name,
                "image": str(container.image.tags[0]) if container.image.tags else str(container.image.short_id),
                "status": container.status,
                "state": container.attrs.get("State", {}).get("Status", "unknown"),
            }

            # Get resource stats only for running containers
            if container.status == "running":
                try:
                    stats = container.stats(stream=False)
                    # Calculate CPU percentage
                    cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                                stats["precpu_stats"]["cpu_usage"]["total_usage"]
                    system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                                   stats["precpu_stats"]["system_cpu_usage"]
                    num_cpus = stats["cpu_stats"]["online_cpus"]

                    if system_delta > 0 and cpu_delta >= 0:
                        info["cpu"] = round((cpu_delta / system_delta) * num_cpus * 100.0, 1)
                    else:
                        info["cpu"] = 0.0

                    # Calculate memory usage
                    mem_usage = stats["memory_stats"].get("usage", 0)
                    mem_limit = stats["memory_stats"].get("limit", 1)
                    # Subtract cache for more accurate reading
                    cache = stats["memory_stats"].get("stats", {}).get("cache", 0)
                    actual_usage = mem_usage - cache

                    info["mem_usage"] = actual_usage
                    info["mem_limit"] = mem_limit
                    info["mem"] = round((actual_usage / mem_limit) * 100.0, 1) if mem_limit > 0 else 0.0

                except Exception:
                    info["cpu"] = 0.0
                    info["mem"] = 0.0
                    info["mem_usage"] = 0
                    info["mem_limit"] = 0
            else:
                info["cpu"] = 0.0
                info["mem"] = 0.0
                info["mem_usage"] = 0
                info["mem_limit"] = 0

            # Created / uptime
            created = container.attrs.get("Created", "")
            info["created"] = created

            containers.append(info)

    except Exception as e:
        logger.error(f"Error collecting Docker stats: {e}")
        # Reset client on connection errors
        global _docker_client, _docker_available
        _docker_client = None
        _docker_available = None

    return containers
