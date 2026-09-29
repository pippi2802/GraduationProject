.PHONY: build test session profile analyze budget validate report clean

PYTHON ?= python3
CONFIG ?= configs/session_profiling.yaml

build:
	$(MAKE) -C stress
	$(PYTHON) -m pip install -r requirements.txt

test:
	tools/run_tests.sh

# --dry-run by default: real sessions/campaigns touch a live cluster and
# stress the node for real, run explicitly with `make session DRY_RUN=`
# (empty) once you've reviewed the dry-run plan.
DRY_RUN ?= --dry-run
session:
	$(PYTHON) -m rq2.orchestration.session $(CONFIG) $(DRY_RUN)

profile:
	$(PYTHON) -m rq2.orchestration.campaign configs/campaign_profiling.yaml $(DRY_RUN)

# Batch 2 (Step 2/3): tail estimation + inflation factors over
# results/raw/<profiling session>, written to results/derived/.
analyze:
	$(PYTHON) -m rq2.procedure.tail_estimation --help
	$(PYTHON) -m rq2.procedure.inflation --help

# Batch 2 (Step 4): derive budgets.json from the analyzed tails.
budget:
	$(PYTHON) -m rq2.procedure.budget --help

validate:
	$(PYTHON) -m rq2.orchestration.campaign configs/campaign_validation.yaml $(DRY_RUN)
	$(PYTHON) -m rq2.validation.validate --help

report:
	$(PYTHON) -m rq2.reporting.figures --help
	$(PYTHON) -m rq2.reporting.tables --help

clean:
	$(MAKE) -C stress clean
	find . -name '__pycache__' -type d -exec rm -rf {} +
