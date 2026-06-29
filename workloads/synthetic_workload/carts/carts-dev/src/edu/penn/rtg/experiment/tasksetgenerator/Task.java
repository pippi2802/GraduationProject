package edu.penn.rtg.experiment.tasksetgenerator;
import java.io.*;
/**
 * Overhead aware task.
 * It's a POJO
 * 
 * JDK version used: <JDK1.7>
 * @author Meng Xu
 * Create Date: 4/4/2013 
 *
 */
public class Task {
	private double period;
	private double exe;
	private double deadline;
	private double delta_rel;	// release overhead
	private double delta_sch;	// schedule overhead
	private double delta_crpmd;	// cache related preemption/migration overhead
	private double delta_cxs;	// context swtich overhead
	private String name;
	
	public Task(){
		this.period = -1;
		this.exe = -1;
		this.deadline = -1;
		this.delta_rel = 0;
		this.delta_sch = 0;
		this.delta_cxs = 0;
		this.delta_crpmd = 0;
		this.name = "default";
	}
	
	public Task(double period, double exe, double deadline){
		this.period = period;
		this.exe = exe;
		this.deadline = deadline;
		this.name = "default";
		this.delta_rel = 0;
		this.delta_sch = 0;
		this.delta_cxs = 0;
		this.delta_crpmd = 0;
	}
	
	public Task(double period, double exe, double deadline, double delta_crpmd, String name){
		this.period = period;
		this.exe = exe;
		this.deadline = deadline;
		this.delta_crpmd = delta_crpmd;
		this.name = name;
		this.delta_rel = 0;
		this.delta_sch = 0;
		this.delta_cxs = 0;
		this.delta_crpmd = 0;
	}
	public Task(String period, String exe, String deadline, String delta_crpmd, String name){
		this.period = Double.parseDouble(period);
		this.exe = Double.parseDouble(exe);
		this.deadline = Double.parseDouble(deadline);
		this.delta_crpmd = Double.parseDouble(delta_crpmd);
		this.name = name;
		this.delta_rel = 0;
		this.delta_sch = 0;
		this.delta_cxs = 0;
		this.delta_crpmd = 0;
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
	public double getDelta_rel() {
		return delta_rel;
	}
	public void setDelta_rel(double delta_rel) {
		this.delta_rel = delta_rel;
	}
	public double getDelta_sch() {
		return delta_sch;
	}
	public void setDelta_sch(double delta_sch) {
		this.delta_sch = delta_sch;
	}
	public double getDelta_crpmd() {
		return delta_crpmd;
	}
	public void setDelta_crpmd(double delta_crpmd) {
		this.delta_crpmd = delta_crpmd;
	}
	public double getDelta_cxs() {
		return delta_cxs;
	}
	public void setDelta_cxs(double delta_cxs) {
		this.delta_cxs = delta_cxs;
	}
	public String getName() {
		return name;
	}
	public void setName(String name) {
		this.name = name;
	}
	
	
	
}
