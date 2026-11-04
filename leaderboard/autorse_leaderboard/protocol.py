"""The versioned public leaderboard protocol, independent of reported results."""
TASK_ORDER = ("hstu", "intsr", "tiger", "onetrans", "rankmixer", "wukong")
DATA_REVISION = "autorse-public-v2-20261029"
PUBLIC_BUNDLE_SHA256 = "4185fa03339cd37df9591906ef1e2e309beec6b3676e724d2c60916b13679414"
RESEARCH_BUDGET_SECONDS = 43200
FINALIZATION_GRACE_SECONDS = 300
TRIALS_PER_TASK = 3
GPUS_PER_RUN = 1
PRIMARY_METRICS = {"hstu": "ndcg_at_10", "intsr": "macro_ndcg_at_10", "tiger": "ndcg_at_10",
                   "onetrans": "auc", "rankmixer": "auc", "wukong": "auc"}
# These identify fixed metric implementations, not the GPU allocation of an agent run.
EVALUATOR_BACKENDS = ("pytorch-fp64-cuda", "numpy-cpu-v1")
LEGACY_EVALUATOR_BACKEND = "pytorch-fp64-cuda"
LEGACY_PARTICIPANT_KIND = "huggingface-account"
PARTICIPANT_KINDS = (LEGACY_PARTICIPANT_KIND, "anonymous-session")
