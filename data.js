window.AUTORSE_DATA = {
  "tasks": [
    {
      "name": "HSTU",
      "type": "Generative recommendation",
      "dataset": "Amazon Beauty",
      "metric": "NDCG@10",
      "baseline_score": 0.0535,
      "method": "Sequential modeling"
    },
    {
      "name": "TIGER",
      "type": "Generative recommendation",
      "dataset": "Amazon Beauty",
      "metric": "NDCG@10",
      "baseline_score": 0.0332,
      "method": "Semantic-ID generation"
    },
    {
      "name": "IntSR",
      "type": "Generative recommendation",
      "dataset": "Amazon Kindle",
      "metric": "Macro NDCG@10",
      "baseline_score": 0.694,
      "method": "Joint search–recommendation modeling"
    },
    {
      "name": "WuKong",
      "type": "CTR prediction",
      "dataset": "MovieLens Latest",
      "metric": "AUC",
      "baseline_score": 0.9645,
      "method": "Feature interaction"
    },
    {
      "name": "RankMixer",
      "type": "CTR prediction",
      "dataset": "Criteo 5M",
      "metric": "AUC",
      "baseline_score": 0.7859,
      "method": "Multi-head token mixing"
    },
    {
      "name": "OneTrans",
      "type": "CTR prediction",
      "dataset": "KuaiSAR v2",
      "metric": "Click AUC",
      "baseline_score": 0.6767,
      "method": "Unified sequence modeling"
    }
  ],
  "mainResults": {
    "headline": "Agents improve performance, but results depend on both task and harness.",
    "mean_relative_gain_percent": 16.1,
    "mean_definition": "Unweighted arithmetic mean of the relative test-score changes across all 42 task–agent configurations, including negative values. Each score is the mean of three trials. The relative gain is 100 × (agent score − baseline score) / baseline score.",
    "positive_configurations": 35,
    "total_configurations": 42,
    "five_tasks": [
      "HSTU",
      "TIGER",
      "OneTrans",
      "RankMixer",
      "WuKong"
    ],
    "task_order": [
      "HSTU",
      "IntSR",
      "TIGER",
      "OneTrans",
      "RankMixer",
      "WuKong"
    ],
    "baseline": [
      0.0535,
      0.694,
      0.0332,
      0.6767,
      0.7859,
      0.9645
    ],
    "rows": [
      {
        "harness": "Claude Code",
        "model": "DeepSeek V4 Flash",
        "scores": [
          0.0674,
          0.6606,
          0.0476,
          0.7467,
          0.7979,
          0.9805
        ],
        "sd": [
          0.0032,
          0.0541,
          0.0138,
          0.0324,
          0.0015,
          0.003
        ],
        "relative_gain_percent": [
          25.98,
          -4.81,
          43.37,
          10.34,
          1.53,
          1.66
        ],
        "average_gain_percent": 13.01
      },
      {
        "harness": "Claude Code",
        "model": "Claude Opus 4.8",
        "scores": [
          0.0754,
          0.7325,
          0.0631,
          0.7184,
          0.8002,
          0.984
        ],
        "sd": [
          0.0043,
          0.0292,
          0.0164,
          0.0068,
          0.0009,
          0.0039
        ],
        "relative_gain_percent": [
          40.93,
          5.55,
          90.06,
          6.16,
          1.82,
          2.02
        ],
        "average_gain_percent": 24.42
      },
      {
        "harness": "Codex",
        "model": "DeepSeek V4 Flash",
        "scores": [
          0.0657,
          0.6485,
          0.0583,
          0.7203,
          0.7974,
          0.979
        ],
        "sd": [
          0.003,
          0.0335,
          0.0147,
          0.0044,
          0.0003,
          0.0018
        ],
        "relative_gain_percent": [
          22.8,
          -6.56,
          75.6,
          6.44,
          1.46,
          1.5
        ],
        "average_gain_percent": 16.88
      },
      {
        "harness": "Codex",
        "model": "GPT-5.5",
        "scores": [
          0.0672,
          0.7692,
          0.0659,
          0.7292,
          0.7954,
          0.9796
        ],
        "sd": [
          0.0065,
          0.1904,
          0.0046,
          0.0342,
          0.003,
          0.0032
        ],
        "relative_gain_percent": [
          25.61,
          10.84,
          98.49,
          7.76,
          1.21,
          1.57
        ],
        "average_gain_percent": 24.24
      },
      {
        "harness": "Terminus-2",
        "model": "DeepSeek V4 Flash",
        "scores": [
          0.0667,
          0.6291,
          0.0554,
          0.6665,
          0.7977,
          0.9877
        ],
        "sd": [
          0.0057,
          0.0858,
          0.0158,
          0.0447,
          0.0012,
          0.002
        ],
        "relative_gain_percent": [
          24.67,
          -9.35,
          66.87,
          -1.51,
          1.5,
          2.41
        ],
        "average_gain_percent": 14.1
      },
      {
        "harness": "Terminus-2",
        "model": "GPT-5.5",
        "scores": [
          0.0697,
          0.6146,
          0.0614,
          0.7285,
          0.7944,
          0.9749
        ],
        "sd": [
          0.0058,
          0.0711,
          0.0053,
          0.0498,
          0.0021,
          0.0035
        ],
        "relative_gain_percent": [
          30.28,
          -11.44,
          84.94,
          7.65,
          1.08,
          1.08
        ],
        "average_gain_percent": 18.93
      },
      {
        "harness": "Terminus-2",
        "model": "Claude Opus 4.8",
        "scores": [
          0.0636,
          0.6761,
          0.0273,
          0.7207,
          0.7989,
          0.9823
        ],
        "sd": [
          0.0015,
          0.0334,
          0.019,
          0.0232,
          0.0014,
          0.0004
        ],
        "relative_gain_percent": [
          18.88,
          -2.58,
          -17.77,
          6.5,
          1.65,
          1.85
        ],
        "average_gain_percent": 1.42
      }
    ]
  },
  "ideas": {
    "model": "DeepSeek V4 Flash",
    "harness": "Claude Code",
    "trials": 3,
    "conditions": [
      "Standard",
      "Self-generated ideas",
      "Idea-injected"
    ],
    "self_generated": "Generate eight candidate ideas and select two or three directions per round.",
    "external_library": "Textual entries distilled from research papers and public competition solutions, spanning architectures, data, training, and inference.",
    "average_score_gain_vs_standard_percent": 14.23,
    "average_score_gain_vs_self_generated_percent": 13.35,
    "average_novelty_gain_vs_standard": 0.76,
    "average_novelty_gain_vs_self_generated": 0.58,
    "task_order": [
      "HSTU",
      "IntSR",
      "TIGER",
      "OneTrans",
      "RankMixer",
      "WuKong"
    ],
    "standard_scores": [
      0.0674,
      0.6606,
      0.0476,
      0.7467,
      0.7979,
      0.9805
    ],
    "self_generated_scores": [
      0.0681,
      0.60724,
      0.0519,
      0.76109,
      0.79403,
      0.98931
    ],
    "idea_injected_scores": [
      0.0831,
      0.75707,
      0.06729,
      0.77729,
      0.79992,
      0.99786
    ],
    "standard_novelty": [
      2.67,
      2.11,
      3.0,
      2.0,
      2.11,
      2.56
    ],
    "self_generated_novelty": [
      3.0,
      2.0,
      3.33,
      2.33,
      2.33,
      2.56
    ],
    "idea_injected_novelty": [
      3.33,
      3.0,
      3.67,
      2.67,
      3.0,
      3.33
    ]
  },
  "abstract": [
    "Recommender Systems Engineer Agents (RSE-Agents), which use LLM-based agents to autonomously improve recommendation algorithms, are emerging as a promising paradigm. However, their capabilities and limitations remain poorly understood due to the lack of a unified, standardized evaluation framework and systematic trajectory-level analysis. To address this gap, we introduce AutoRSE, an evaluation framework spanning six representative industrial-grade recommendation tasks, and conduct a large-scale empirical study of three frontier LLMs across three widely used agent harnesses.",
    "Our results show that RSE-Agents consistently enhance the performance of backbones on five of the six tasks, with an average relative improvement of 16.1%, indicating that they can already autonomously improve recommendation performance. However, trajectory-level analysis also reveals that current RSE-Agents function primarily as engineering optimizers rather than algorithmic improvers: their gains are largely driven by hyperparameter tuning, training strategies, and model ensembling, while genuine algorithmic innovations are rare. Since the largest gains in recommender systems often stem from algorithmic advances, this behavior underscores a fundamental limitation of current RSE-Agents.",
    "To probe this limitation, we perform idea-injection experiments and show that agents equipped with innovative ideas from frontier research or human experts achieve substantially larger improvements than those relying on self-generated ideas. These results suggest that idea generation is a central bottleneck of current RSE-Agents, highlights a key direction for the future recommendation system research. Our implementation is publicly available on GitHub: https://github.com/Ray-Tiann/AutoRSE."
  ]
};
