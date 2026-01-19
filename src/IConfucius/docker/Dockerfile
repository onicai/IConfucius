ARG IMAGE
FROM --platform=linux/amd64 ${IMAGE}

# Structure mirrors the source repo:
# /app/IConfucius/src/Main.mo
# /app/common/Types.mo
# This allows import "../../common/Types" to work correctly

WORKDIR /app/IConfucius

# Copy project files
COPY IConfucius/mops.toml ./
COPY IConfucius/dfx.json ./
COPY IConfucius/canister_ids.json ./

# Install mops dependencies
RUN mops install

# Copy source files
COPY IConfucius/src /app/IConfucius/src/
COPY common /app/common/
COPY IConfucius/di[d] /app/IConfucius/did/
COPY IConfucius/scripts /app/IConfucius/scripts/

CMD ["/bin/bash"]
