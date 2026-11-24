# Runner GitHub Actions auto-hébergé (Linux) de Party : image officielle de GitHub + gh et venv.
# Version épinglée ; le runner se met à jour tout seul ensuite (GitHub l'exige), et redevient celle-ci au redémarrage.
FROM ghcr.io/actions/actions-runner:2.338.2
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends gh python3-venv python3-pip \
 && rm -rf /var/lib/apt/lists/*
COPY --chmod=755 entrypoint.sh /usr/local/bin/party-runner
USER runner
ENTRYPOINT ["/usr/local/bin/party-runner"]
