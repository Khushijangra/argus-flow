# NEXUS-ATMS: A Recruiter's Overview

## What This Project Does

NEXUS-ATMS is an end-to-end, AI-powered traffic management system. Traditional traffic lights run on simple, fixed timers—they turn green or red on a strict schedule regardless of how many cars are actually waiting. This rigidity creates massive traffic jams during rush hours or unpredictable accidents.

This project completely replaces those "dumb" timers with an intelligent "brain." By using a specialized type of Artificial Intelligence known as Deep Reinforcement Learning (specifically, a D3QN algorithm), the system constantly looks at a simulated intersection, evaluates the current traffic buildup, and dynamically chooses the best possible traffic light phase to keep cars moving smoothly. 

In addition to controlling the lights, the system features an anomaly detection engine to automatically flag traffic accidents, and it includes a fast, modern backend architecture (built with FastAPI) that streams this data to a live operator dashboard.

## Why It Matters

Urban traffic congestion is estimated to cost the global economy over $1.7 trillion annually in lost productivity and wasted fuel. Furthermore, vehicles idling at red lights unnecessarily emit massive amounts of carbon dioxide (CO₂) and delay critical emergency responders like ambulances.

By proving that an AI can adapt to changing traffic conditions in real-time, NEXUS-ATMS demonstrates a pathway to significantly reducing commute times, cutting down urban carbon emissions, and allowing emergency vehicles to navigate cities safely and swiftly through automated "green-wave" corridors.

## Technologies Used

To build a production-like system, this project utilized a modern, full-stack machine learning technology stack:

- **Machine Learning & AI**: Python, PyTorch (for neural network training), Scikit-learn.
- **Backend Infrastructure**: FastAPI (for building the API), Uvicorn, WebSockets (for live data streaming).
- **Simulation Engine**: Eclipse SUMO (the industry standard for realistic microscopic traffic simulation).
- **Testing & DevOps**: Pytest (for automated quality assurance), GitHub Actions (for Continuous Integration pipelines).

## Verified Outcomes

The system was rigorously evaluated in a controlled simulation environment against a standard fixed-time baseline. The algorithmic improvements resulted in the following verified metrics:

- **Massive Time Savings**: The AI reduced average vehicle waiting times at intersections from **571.1 seconds down to just 10.2 seconds**—a massive **98.2% reduction**.
- **Algorithmic Reliability**: The AI's performance was incredibly stable across multiple randomized traffic scenarios, consistently clearing intersections in **9.96 ± 0.24 seconds**.
- **Accident Detection**: The ensemble anomaly detection model achieved an F1 Score of **0.913** and a perfect Recall of **1.000**, ensuring that simulated accidents were never missed.

## Why This Demonstrates Internship Readiness

While many student portfolios feature simple, isolated machine learning models (like a basic Python script running in a Jupyter Notebook), NEXUS-ATMS demonstrates **Full-Stack ML Engineering**. 

To be successful at top-tier technology companies, an engineer must understand how to deploy models into complex systems. This project highlights crucial enterprise engineering skills:
1. **Architectural Thinking**: Refactoring a complex, 3,000-line monolithic codebase into a scalable, decoupled micro-architecture using the industry-standard "Strangler Fig" pattern.
2. **Operational Excellence**: Writing rigorous Pytest testing suites and configuring automated CI/CD pipelines to ensure code reliability.
3. **Data Integrity**: Prioritizing safety and mathematical verification over inflated claims, proven by the strict multi-seed statistical evaluation of the AI models.
4. **End-to-End Ownership**: Taking a complex theoretical problem (Reinforcement Learning) and successfully wrapping it in a robust software service layer (FastAPI) that a frontend dashboard can actually consume.

This repository demonstrates the rare ability to bridge the gap between theoretical AI research and practical, maintainable software engineering.
