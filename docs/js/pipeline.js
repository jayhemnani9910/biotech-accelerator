/**
 * Pipeline animation controller for Biotech Research Accelerator demo
 */

class Pipeline {
    constructor() {
        // Stage order follows the README pipeline
        this.nodeOrder = ['parser', 'uniprot', 'pubmed', 'structure', 'chembl', 'synthesis', 'experiments'];
        this.nodes = {};
        for (const nodeName of this.nodeOrder) {
            this.nodes[nodeName] = document.getElementById(`node-${nodeName}`);
        }
    }

    /**
     * Reset all nodes to initial state
     */
    reset() {
        for (const nodeName of this.nodeOrder) {
            const node = this.nodes[nodeName];
            node.classList.remove('active', 'complete', 'skipped');

            // Clear status
            const status = node.querySelector('.node-status');
            status.innerHTML = '';

            // Clear output
            const output = node.querySelector('.node-output');
            output.textContent = '';
        }
    }

    /**
     * Activate a node (show spinner)
     */
    activateNode(nodeName) {
        const node = this.nodes[nodeName];
        if (!node) return;

        // Remove previous states
        node.classList.remove('complete');
        node.classList.add('active');

        // Add spinner
        const status = node.querySelector('.node-status');
        status.innerHTML = '<div class="spinner"></div>';
    }

    /**
     * Complete a node (show checkmark)
     */
    completeNode(nodeName, outputText = '') {
        const node = this.nodes[nodeName];
        if (!node) return;

        // Update state
        node.classList.remove('active');
        node.classList.add('complete');

        // Remove spinner (checkmark added via CSS ::after)
        const status = node.querySelector('.node-status');
        status.innerHTML = '';

        // Set output text
        if (outputText) {
            const output = node.querySelector('.node-output');
            output.textContent = outputText;
        }
    }

    /**
     * Run a single step animation
     */
    async runStep(step, terminal) {
        const { node, delay, output, terminalOutput } = step;

        // Activate the node
        this.activateNode(node);

        // Add terminal output lines
        if (terminal && terminalOutput) {
            await terminal.addOutputLines(terminalOutput);
        }

        // Wait for the step duration
        await this.sleep(delay);

        // Complete the node
        this.completeNode(node, output);
    }

    /**
     * Mark a stage the scenario does not use (e.g. CHEMBL for a non-drug query)
     */
    skipNode(nodeName) {
        const node = this.nodes[nodeName];
        if (!node) return;

        node.classList.add('skipped');
        node.querySelector('.node-output').textContent = 'skipped';
    }

    /**
     * Run all stages in pipeline order; stages without a step are skipped
     */
    async runAllSteps(steps, terminal) {
        for (const nodeName of this.nodeOrder) {
            const step = steps.find(s => s.node === nodeName);
            if (step) {
                await this.runStep(step, terminal);
            } else {
                this.skipNode(nodeName);
            }
            await this.sleep(300); // Brief pause between nodes
        }
    }

    /**
     * Sleep utility
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Pipeline;
}
