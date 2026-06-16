# SAM custom build (Metadata.BuildMethod: makefile in infra/template.yaml).
# Runs during `sam build` with NO container: pip pulls prebuilt Linux/arm64
# wheels for Python 3.12 directly, then we copy the app + entrypoint into the
# build artifact dir SAM hands us via $(ARTIFACTS_DIR).
#
# Requires python3 + pip on PATH (no Docker). If a future dependency lacks a
# prebuilt arm64 wheel, this fails — switch back to `sam build --use-container`.
.PHONY: build-ChatFunction
build-ChatFunction:
	python3 -m pip install --only-binary=:all: --platform manylinux2014_aarch64 --python-version 3.12 --implementation cp --abi cp312 -r requirements.txt -t "$(ARTIFACTS_DIR)"
	cp -r app run.sh "$(ARTIFACTS_DIR)"
