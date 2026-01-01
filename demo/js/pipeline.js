/**
 * Pipeline animation controller for Biotech Research Accelerator demo
 */

class Pipeline {
    constructor() {
        this.nodes = {
            parser: document.getElementById('node-parser'),
            uniprot: document.getElementById('node-uniprot'),
            pubmed: document.getElementById('node-pubmed'),
            structure: document.getElementById('node-structure'),
            synthesis: document.getElementById('node-synthesis')
        };
        this.nodeOrder = ['parser', 'uniprot', 'pubmed', 'structure', 'synthesis'];
    }

    /**
     * Reset all nodes to initial state
     */
    reset() {
        for (const nodeName of this.nodeOrder) {
            const node = this.nodes[nodeName];
            node.classList.remove('active', 'complete');

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
     * Run all steps in sequence
     */
    async runAllSteps(steps, terminal) {
        for (const step of steps) {
            await this.runStep(step, terminal);
            await this.sleep(300); // Brief pause between nodes
        }
    }

    /**
     * Get node element
     */
    getNode(nodeName) {
        return this.nodes[nodeName];
    }

    /**
     * Check if all nodes are complete
     */
    isComplete() {
        return this.nodeOrder.every(name =>
            this.nodes[name].classList.contains('complete')
        );
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
