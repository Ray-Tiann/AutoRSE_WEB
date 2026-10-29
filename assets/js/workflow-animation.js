(function () {
  'use strict';

  const root = document.getElementById('workflow-animation');
  if (!root) return;

  const states = [
    {
      stage: 'initialize', phase: 'initialize', label: 'Initialize the task',
      title: 'Start from a complete recommendation baseline.',
      copy: 'The agent receives the task description, baseline code, training and validation data, and unlabeled test inputs. Ground-truth test labels remain hidden.'
    },
    {
      stage: 'explore', phase: 'research', label: 'Research loop · Explore',
      title: 'Understand the task, code, and data.',
      copy: 'Inspect the reference codebase and dataset to understand the recommendation objective, evaluation metric, and existing training pipeline.'
    },
    {
      stage: 'ideate', phase: 'research', label: 'Research loop · Ideate',
      title: 'Propose an improvement to the baseline.',
      copy: 'Form an optimization hypothesis using the task requirements and available evidence, then decide which change to test.'
    },
    {
      stage: 'implement', phase: 'research', label: 'Research loop · Implement',
      title: 'Turn the hypothesis into executable code.',
      copy: 'Edit the recommendation code and supporting configuration to implement the proposed change within the execution environment.'
    },
    {
      stage: 'experiment', phase: 'research', label: 'Research loop · Experiment',
      title: 'Run training and validation.',
      copy: 'Execute the modified pipeline within the available compute budget. Training logs, errors, and validation metrics provide feedback; test labels remain hidden.'
    },
    {
      stage: 'analyze', phase: 'research', label: 'Research loop · Analyze',
      title: 'Decide what to retain, revise, or discard.',
      copy: 'Analyze execution feedback and validation results to assess the modification and guide the next optimization cycle.'
    },
    {
      stage: 'analyze', phase: 'feedback', label: 'Validation feedback → next idea', duration: 2200,
      title: 'Use validation feedback to refine the strategy.',
      copy: 'Feed the observed results back into the next hypothesis. The agent may repeat this research loop while budget remains, using validation evidence to guide each revision.'
    },
    {
      stage: 'ideate', phase: 'research', label: 'Research loop · Refine the idea',
      title: 'Let the previous experiment inform the next idea.',
      copy: 'Revise the optimization hypothesis using validation evidence and execution feedback from the previous cycle.'
    },
    {
      stage: 'implement', phase: 'research', label: 'Research loop · Revise the code',
      title: 'Implement the next candidate strategy.',
      copy: 'Update the executable recommendation code to test the revised hypothesis, continuing from the available baseline and experimental evidence.'
    },
    {
      stage: 'experiment', phase: 'research', label: 'Research loop · Test the revision',
      title: 'Train and validate the revised candidate.',
      copy: 'Run another experiment and collect validation metrics, logs, and errors. Final test labels are still unavailable to the agent.'
    },
    {
      stage: 'analyze', phase: 'research', label: 'Research loop · Review the evidence',
      title: 'Compare candidates using validation feedback.',
      copy: 'Review the accumulated experimental evidence and select which strategy to retain within the remaining computational budget.'
    },
    {
      stage: 'analyze', phase: 'budget', label: '12-hour budget reached', duration: 2200,
      title: 'Budget reached. Prepare the final artifacts.',
      copy: 'When the 12-hour budget ends, optimization stops. The agent prepares the final recommendation strategy π_final and its test-set predictions Ŷ_final for submission.'
    },
    {
      stage: 'submit', phase: 'submit', label: 'Submit the final artifacts', duration: 2200,
      title: 'Submit the final strategy and predictions.',
      copy: 'The final recommendation strategy π_final and predictions Ŷ_final pass to the evaluation framework after the research budget ends.'
    },
    {
      stage: 'verify', phase: 'verify', label: 'Evaluate against hidden test labels', duration: 2200,
      title: 'Evaluate predictions on the held-out test set.',
      copy: 'The framework compares Ŷ_final against ground-truth test labels using the task’s evaluation metric. These labels were hidden throughout the agent’s optimization process.'
    },
    {
      stage: 'score', phase: 'score', label: 'Final score',
      title: 'Report the final held-out performance.',
      copy: 'The framework reports the task’s primary metric on held-out test labels, providing a consistent measure of the submitted strategy’s recommendation performance.'
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
  const detailCopy = root.querySelector('#wf-detail-copy');
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
    setText(detailCopy, state.copy);
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
