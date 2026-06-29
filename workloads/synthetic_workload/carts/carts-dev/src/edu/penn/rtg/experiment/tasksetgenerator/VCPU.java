package edu.penn.rtg.experiment.tasksetgenerator;
import java.util.*;

public class VCPU {
	private double period;
	private double exe;
	private double deadline;
	private int domAffinity; //which dom this vcpu belongs to
	private int cpu; //only used for partitioned algorithm. not consider cluster yet 
	private Vector<Task> taskset;
	private double usedUtil;
	private String name;
	
	public VCPU(){
		this.period = -1;
		this.exe = -1;
		this.deadline = -1;
		this.domAffinity = -1; 
		this.cpu = -1;
		this.usedUtil = 0;
		this.taskset = new Vector<Task>();
	}

	public VCPU(double util){
		this.usedUtil = util;
		this.period = -1;
		this.exe = -1;
		this.deadline = -1;
		this.domAffinity = -1; 
		this.cpu = -1;
		this.taskset = new Vector<Task>();
	}
	
	public VCPU(String period, String exe, String deadline, int domAffinity){
		this.period = Double.parseDouble(period) ;
		this.exe = Double.parseDouble(exe);
		this.deadline = Double.parseDouble(deadline);
		this.domAffinity = domAffinity;
		this.cpu = -1;
		this.taskset = new Vector<Task>();
	}
	
	
	public double getPeriod() {
		return period;
	}
	public void setPeriod(double period) {
		this.period = period;
	}
	public double getExe() {
		return exe;
	}
	public void setExe(double exe) {
		this.exe = exe;
	}
	public double getDeadline() {
		return deadline;
	}
	public void setDeadline(double deadline) {
		this.deadline = deadline;
	}
	public int getCpu() {
		return cpu;
	}
	public void setCpu(int cpu) {
		this.cpu = cpu;
	}

	public int getDomAffinity() {
		return domAffinity;
	}

	public void setDomAffinity(int domAffinity) {
		this.domAffinity = domAffinity;
	}

	public Vector<Task> getTaskset() {
		return taskset;
	}

	public void setTaskset(Vector<Task> taskset) {
		this.taskset = taskset;
	}

	public double getUsedUtil() {
		return usedUtil;
	}

	public void setUsedUtil(double usedUtil) {
		this.usedUtil = usedUtil;
	}

	public String getName() {
		return name;
	}

	public void setName(String name) {
		this.name = name;
	}
	
	
	
}
