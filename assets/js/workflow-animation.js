(function () {
  'use strict';

  const root = document.getElementById('workflow-animation');
  if (!root) return;

  const states = [
    {
      stage: 'initialize', phase: 'initialize', label: 'Initialize',
      title: "Start from a recommendation baseline.",
    },
    {
      stage: 'explore', phase: 'research', label: 'Explore',
      title: "Inspect the task, code, and data.",
    },
    {
      stage: 'ideate', phase: 'research', label: 'Ideate',
      title: "Propose an improvement.",
    },
    {
      stage: 'implement', phase: 'research', label: 'Implement',
      title: "Implement the idea.",
    },
    {
      stage: 'experiment', phase: 'research', label: 'Experiment',
      title: "Train and validate.",
    },
    {
      stage: 'analyze', phase: 'research', label: 'Analyze',
      title: "Analyze validation and execution feedback.",
    },
    {
      stage: 'analyze', phase: 'feedback', label: 'Feedback', duration: 2200,
      title: "Use feedback to refine the strategy.",
    },
    {
      stage: 'ideate', phase: 'research', label: 'Refine the idea',
      title: "Refine the idea.",
    },
    {
      stage: 'implement', phase: 'research', label: 'Revise the code',
      title: "Update the code.",
    },
    {
      stage: 'experiment', phase: 'research', label: 'Test the revision',
      title: "Train and validate again.",
    },
    {
      stage: 'analyze', phase: 'research', label: 'Review the evidence',
      title: "Compare the candidates.",
    },
    {
      stage: 'analyze', phase: 'budget', label: '12 h reached', duration: 2200,
      title: "Stop when the 12-hour budget ends.",
    },
    {
      stage: 'submit', phase: 'submit', label: 'Submit', duration: 2200,
      title: "Submit π_final and Ŷ_final.",
    },
    {
      stage: 'verify', phase: 'verify', label: 'Evaluate', duration: 2200,
      title: "Compare predictions with hidden test labels.",
    },
    {
      stage: 'score', phase: 'score', label: 'Final score',
      title: "Report the task’s primary metric.",
    }
  ];

  const stageOrder = ['initialize', 'explore', 'ideate', 'implement', 'experiment', 'analyze', 'submit', 'verify', 'score'];
  const budgetIndex = states.findIndex(function (state) { return state.phase === 'budget'; });
  const nodes = Array.from(root.querySelectorAll('[data-wf-stage]'));
  const stageButtons = nodes.filter(function (node) { return node.matches('button'); });
  const toggle = root.querySelector('#wf-toggle');
  const replay = root.querySelector('#wf-replay');
  const status = root.querySelector('#wf-status');
  const detailTitle = root.querySelector('#wf-detail-title');
  const budgetState = root.querySelector('#wf-budget-state');
  const progress = root.querySelector('#wf-progress');
  const stepCount = root.querySelector('#wf-step-count');
  const announcement = root.querySelector('#wf-announcement');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  let index = 0;
  let timer = null;
  let started = false;
  let manuallyPaused = reducedMotion.matches;
  let visible = false;
  let finished = false;
  let disposed = false;
  let observer = null;
  let environmentListening = false;

  function setText(element, text) {
    if (element) element.textContent = text;
  }

  function announceState() {
    setText(announcement, states[index].label + '. ' + states[index].title);
  }

  function updatePlayback() {
    const playing = timer !== null;
    root.classList.toggle('is-playing', playing);
    if (toggle) {
      toggle.textContent = playing ? 'Pause' : 'Play';
      toggle.setAttribute('aria-label', playing ? 'Pause the workflow animation' : 'Play the workflow animation');
    }
  }

  function stopTimer() {
    if (timer !== null) {
      window.clearTimeout(timer);
      timer = null;
    }
    updatePlayback();
  }

  function render() {
    const state = states[index];
    const activeRank = stageOrder.indexOf(state.stage);
    root.dataset.phase = state.phase;
    root.dataset.stage = state.stage;

    nodes.forEach(function (node) {
      const active = node.dataset.wfStage === state.stage;
      const rank = stageOrder.indexOf(node.dataset.wfStage);
      node.classList.toggle('is-active', active);
      node.classList.toggle('is-complete', rank >= 0 && rank < activeRank);
      if (node.matches('button')) node.setAttribute('aria-pressed', String(active));
    });

    setText(status, state.label);
    setText(detailTitle, state.title);
    setText(budgetState, index >= budgetIndex ? '12 h reached' : '12 h total wall-clock budget');
    setText(stepCount, String(index + 1).padStart(2, '0') + ' / ' + String(states.length));
    if (progress) {
      const fraction = Math.min(index / budgetIndex, 1);
      progress.style.setProperty('--progress', String(fraction));
      progress.setAttribute('aria-valuenow', String(Math.round(fraction * 100)));
      progress.setAttribute('aria-valuetext', index >= budgetIndex ? 'Research budget reached; final evaluation follows.' : 'Illustrated progress through the research budget.');
    }
  }

  function schedule() {
    if (disposed || manuallyPaused || !visible || document.hidden || finished || timer !== null) {
      updatePlayback();
      return;
    }
    timer = window.setTimeout(function () {
      timer = null;
      if (disposed || manuallyPaused || !visible || document.hidden) {
        updatePlayback();
        return;
      }
      if (index < states.length - 1) index += 1;
      render();
      if (index === states.length - 1) {
        finished = true;
        updatePlayback();
        announceState();
      } else {
        schedule();
      }
    }, states[index].duration || 1800);
    updatePlayback();
  }

  function play() {
    started = true;
    manuallyPaused = false;
    if (finished) {
      index = 0;
      finished = false;
      render();
    }
    announceState();
    schedule();
  }

  if (toggle) {
    toggle.addEventListener('click', function () {
      if (timer !== null) {
        manuallyPaused = true;
        stopTimer();
        announceState();
      } else {
        play();
      }
    });
  }

  if (replay) {
    replay.addEventListener('click', function () {
      stopTimer();
      index = 0;
      finished = false;
      started = true;
      manuallyPaused = reducedMotion.matches;
      render();
      announceState();
      schedule();
    });
  }

  stageButtons.forEach(function (button, buttonIndex) {
    button.addEventListener('click', function () {
      const nextIndex = states.findIndex(function (state) { return state.stage === button.dataset.wfStage; });
      if (nextIndex < 0) return;
      manuallyPaused = true;
      started = true;
      stopTimer();
      index = nextIndex;
      finished = index === states.length - 1;
      render();
      announceState();
    });

    button.addEventListener('keydown', function (event) {
      let nextButtonIndex = buttonIndex;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') nextButtonIndex = (buttonIndex + 1) % stageButtons.length;
      else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') nextButtonIndex = (buttonIndex - 1 + stageButtons.length) % stageButtons.length;
      else if (event.key === 'Home') nextButtonIndex = 0;
      else if (event.key === 'End') nextButtonIndex = stageButtons.length - 1;
      else return;
      event.preventDefault();
      stageButtons[nextButtonIndex].focus();
      stageButtons[nextButtonIndex].click();
    });
  });

  function handleVisibility() {
    if (document.hidden) stopTimer();
    else if (started) schedule();
  }

  function handleReducedMotionChange(event) {
    if (event.matches) {
      manuallyPaused = true;
      stopTimer();
    }
  }

  function listenToEnvironment() {
    if (environmentListening) return;
    document.addEventListener('visibilitychange', handleVisibility);
    if (reducedMotion.addEventListener) reducedMotion.addEventListener('change', handleReducedMotionChange);
    else if (reducedMotion.addListener) reducedMotion.addListener(handleReducedMotionChange);
    environmentListening = true;
  }

  function stopListeningToEnvironment() {
    if (!environmentListening) return;
    document.removeEventListener('visibilitychange', handleVisibility);
    if (reducedMotion.removeEventListener) reducedMotion.removeEventListener('change', handleReducedMotionChange);
    else if (reducedMotion.removeListener) reducedMotion.removeListener(handleReducedMotionChange);
    environmentListening = false;
  }

  listenToEnvironment();

  render();
  updatePlayback();

  if ('IntersectionObserver' in window) {
    observer = new IntersectionObserver(function (entries) {
      if (disposed) return;
      const entry = entries[entries.length - 1];
      visible = entry.isIntersecting;
      if (!visible) {
        stopTimer();
        return;
      }
      if (!started && entry.intersectionRatio >= 0.3) started = true;
      if (started) schedule();
    }, { threshold: [0, 0.3] });
    observer.observe(root);
  } else {
    visible = true;
    started = true;
    schedule();
  }

  window.addEventListener('pagehide', function () {
    disposed = true;
    visible = false;
    stopTimer();
    if (observer) observer.disconnect();
    stopListeningToEnvironment();
  });

  window.addEventListener('pageshow', function (event) {
    if (!event.persisted || !disposed) return;
    disposed = false;
    listenToEnvironment();
    if (observer) {
      observer.observe(root);
    } else {
      visible = true;
      if (started) schedule();
    }
  });
}());
