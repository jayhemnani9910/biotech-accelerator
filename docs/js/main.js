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
                    this.runDemo(demoName);
                }
            });
        });

        // Auto-start first demo after a brief delay
        setTimeout(() => {
            this.runDemo('lysozyme');
        }, 500);
    }

    /**
     * Run a demo scenario
     */
    async runDemo(demoName) {
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
            await this.showReport(scenario.report);

        } catch (error) {
            console.error('Demo error:', error);
            this.terminal.addOutputLine(`Error: ${error.message}`, 'warning');
        }

        this.isRunning = false;
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
    async showReport(markdownContent) {
        // Parse markdown
        if (typeof marked !== 'undefined') {
            this.reportContent.innerHTML = marked.parse(markdownContent);
        } else {
            // Fallback: simple markdown rendering
            this.reportContent.innerHTML = this.simpleMarkdown(markdownContent);
        }

        // Show report section with animation
        this.reportSection.classList.add('visible');

        // Scroll to report
        await this.sleep(300);
        this.reportSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    /**
     * Hide the report section
     */
    hideReport() {
        this.reportSection.classList.remove('visible');
        this.reportContent.innerHTML = '';
    }

    /**
     * Simple markdown fallback
     */
    simpleMarkdown(text) {
        return text
            .replace(/^### (.*$)/gm, '<h3>$1</h3>')
            .replace(/^## (.*$)/gm, '<h2>$1</h2>')
            .replace(/^# (.*$)/gm, '<h1>$1</h1>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/^- (.*$)/gm, '<li>$1</li>')
            .replace(/^(\d+)\. (.*$)/gm, '<li>$2</li>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/^---$/gm, '<hr>')
            .replace(/\|(.+)\|/g, (match) => {
                const cells = match.split('|').filter(c => c.trim());
                return '<tr>' + cells.map(c => `<td>${c.trim()}</td>`).join('') + '</tr>';
            });
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
