FROM emqx/emqx:5.8.9@sha256:35b46f7aa7a0d51f3959e4344221ac5ec7f948b03e43099286b6c40a07bb393b

COPY deploy/platform-poc1/emqx/emqx.conf /tmp/openaut.conf
RUN cat /tmp/openaut.conf >> /opt/emqx/etc/emqx.conf
