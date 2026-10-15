# Task 45's libphonenumber dispatcher (docs/BACKLOG.md) -- same dispatcher pattern proven in
# Task 43, toolchain baked in for the actual target repo instead of a bare `git`-only image.
# Java 21 / Maven 3.9.x pinned to match docs/SETUP.md's own confirmed-already-installed Cloud
# Shell versions (Java 21 / Maven 3.9.16) for the LOCAL execution path -- keeping the two
# execution backends on the same real toolchain version is what makes this a fair re-test of
# issue #8, not a different environment producing a coincidentally-similar result.
FROM maven:3.9.9-eclipse-temurin-21

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Real, load-bearing perf fix, 2026-09-27: a Cloud Run Sandbox is one-shot per `sandbox do`
# invocation -- no .m2 cache persists between calls, so every single sandboxed `mvn` call was
# re-downloading libphonenumber's entire dependency tree from Maven Central from scratch, real
# runs observed taking long enough to outlast a Cloud Shell session. Sandboxes get READ-ONLY
# access to this container's own filesystem (confirmed real, task 43's own finding) -- baking a
# pre-resolved /root/.m2 into the image itself means every sandbox invocation sees it already
# populated, no re-download needed. `dependency:go-offline` also resolves plugin dependencies
# (surefire, compiler), not just direct ones. `|| true`: a network hiccup during the image build
# itself shouldn't fail the whole build -- worst case here is falling back to the old
# every-call-downloads-fresh behavior, not a broken image.
RUN git clone --quiet --depth 1 https://github.com/sudsk/libphonenumber.git /tmp/libphonenumber-warmup \
    && cd /tmp/libphonenumber-warmup \
    && (mvn -q -pl java/libphonenumber dependency:go-offline || true) \
    && rm -rf /tmp/libphonenumber-warmup

WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --break-system-packages -r requirements.txt
COPY main.py .

WORKDIR /app
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
