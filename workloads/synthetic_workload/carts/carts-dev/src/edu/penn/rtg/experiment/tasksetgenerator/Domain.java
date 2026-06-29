package edu.penn.rtg.experiment.tasksetgenerator;
import java.util.*;


public class Domain {
	private Vector<Task> taskset;
	private Vector<VCPU> VCPUs;
	private String domName;
	private String period;
	
	public Domain(){
		this.taskset = new Vector<Task>();
		this.VCPUs = new Vector<VCPU>();
	}
	
	public Domain(Vector<Task> taskset, Vector<VCPU> vCPUs, String domName) {
		super();
		this.taskset = taskset;
		VCPUs = vCPUs;
		this.domName = domName;
	}
	public Vector<Task> getTaskset() {
		return taskset;
	}
	public void setTaskset(Vector<Task> taskset) {
		this.taskset = taskset;
	}
	public Vector<VCPU> getVCPUs() {
		return VCPUs;
	}
	public void setVCPUs(Vector<VCPU> vCPUs) {
		VCPUs = vCPUs;
	}
	public String getDomName() {
		return domName;
	}
	public void setDomName(String domName) {
		this.domName = domName;
	}

	public String getPeriod() {
		return period;
	}

	public void setPeriod(String period) {
		this.period = period;
	}
	
}
