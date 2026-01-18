FROM registry.gitlab.steamos.cloud/steamrt/sniper/sdk

RUN apt-get update \
    && apt-get install -y --no-install-recommends --no-install-suggests \
        python3 \
        python3-pip \
        python3-requests \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash steam \
    && mkdir -p /opt/steamcmd \
    && chown steam:steam /opt/steamcmd

USER steam
WORKDIR /home/steam

RUN python3 -m pip install --no-cache-dir pyjson5 \
    && cd /opt/steamcmd \
    && curl -sqL "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz" | tar zxvf -

ENV PATH="/opt/steamcmd:${PATH}"
ENV PYTHONUNBUFFERED=1

COPY --chown=steam:steam src/*.py /src/

ENTRYPOINT ["python3", "/src/entrypoint.py"]