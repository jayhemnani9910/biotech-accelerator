/**
 * Main demo orchestration for Biotech Research Accelerator
 */

class BiotechDemo {
    constructor() {
        this.terminal = new Terminal({ typingSpeed: 40, lineDelay: 150 });
        this.pipeline = new Pipeline();
        this.reportSection = document.getElementById('report-section');
        this.reportContent = document.getElementById('report-content');
        this.demoButtons = document.querySelectorAll('.demo-btn');
        this.isRunning = false;
        this.currentDemo = null;

        this.init();
    }

    /**
     * Initialize demo
     */
    init() {
        // Set up button click handlers
        this.demoButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                if (!this.isRunning) {
                    const demoName = btn.dataset.demo;
                    this.runDemo(demoName, { scroll: true });
                }
            });
        });

        // Auto-start first demo after a brief delay. It does not scroll: the
        // visitor may have moved elsewhere on the page by the time it finishes.
        setTimeout(() => {
            this.runDemo('lysozyme');
        }, 500);
    }

    /**
     * Run a demo scenario. `scroll` brings the report into view when it is ready.
     */
    async runDemo(demoName, { scroll = false } = {}) {
        if (this.isRunning) return;
        if (!DEMO_SCENARIOS[demoName]) {
            console.error(`Unknown demo: ${demoName}`);
            return;
        }

        this.isRunning = true;
        this.currentDemo = demoName;

        // Update button states
        this.updateButtonStates(demoName);

        // Reset everything
        this.reset();

        const scenario = DEMO_SCENARIOS[demoName];

        try {
            // Phase 1: Type the query
            await this.terminal.typeText(scenario.query);
            await this.sleep(500);

            // Phase 2: Show "Running pipeline..."
            this.terminal.hideCursor();
            this.terminal.addOutputLine('');
            this.terminal.addOutputLine('Running pipeline...', 'info');
            await this.sleep(800);

            // Phase 3: Run pipeline steps
            await this.pipeline.runAllSteps(scenario.steps, this.terminal);

            // Phase 4: Show completion
            this.terminal.addOutputLine('');
            this.terminal.addOutputLine('Pipeline complete!', 'success');
            await this.sleep(500);

            // Phase 5: Render report
            await this.showReport(scenario.report, scroll);

        } catch (error) {
            console.error('Demo error:', error);
            this.terminal.addOutputLine(`Error: ${error.message}`, 'warning');
        } finally {
            this.isRunning = false;
            this.updateButtonStates(demoName);
        }
    }

    /**
     * Reset demo state
     */
    reset() {
        this.terminal.reset();
        this.pipeline.reset();
        this.hideReport();
    }

    /**
     * Show the research report
     */
    async showReport(markdownContent, scroll) {
        if (typeof marked !== 'undefined') {
            this.reportContent.innerHTML = marked.parse(markdownContent);
        } else {
            // marked failed to load: show the markdown source as plain text
            const pre = document.createElement('pre');
            pre.className = 'report-raw';
            pre.textContent = markdownContent;
            this.reportContent.replaceChildren(pre);
        }

        // Show report section with animation
        this.reportSection.classList.add('visible');

        if (scroll) {
            await this.sleep(300);
            this.reportSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    /**
     * Hide the report section
     */
    hideReport() {
        this.reportSection.classList.remove('visible');
        this.reportContent.innerHTML = '';
    }

    /**
     * Update button active states
     */
    updateButtonStates(activeDemoName) {
        this.demoButtons.forEach(btn => {
            const isActive = btn.dataset.demo === activeDemoName;
            btn.classList.toggle('active', isActive);
            btn.disabled = this.isRunning;
        });
    }

    /**
     * Sleep utility
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.biotechDemo = new BiotechDemo();
});
