package edu.penn.rtg.schedulingapp.basic;

public class PTask {
	public int period;
	public double exec;
	public int deadline;
	public PTask(int period, double exec) {
		this.period = period;
		this.deadline = period;
		this.exec = exec;
	}
	public PTask(int period, double exec, int deadline) {
		this.period = period;
		this.exec = exec;
		this.deadline = deadline;
	}
}
