from redis_client import create_redis_client


def test_redis_connection() -> None:
    client = create_redis_client()
    try:
        assert client.ping() is True
        print("Redis connection successful.")
    finally:
        client.close()


if __name__ == "__main__":
    test_redis_connection()