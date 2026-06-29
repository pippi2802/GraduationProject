package edu.penn.rtg.csa.dmpr;
import java.io.*;

import edu.penn.rtg.common.Tool;
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
	
	/*
	 * Get the workload bound of tau_i to tau_k
	 * Equation 3 of Arvind's paper in 09
	 */
	public double getWorkload(double t){
		double CI_t = Math.min(exe, Math.max(0, t - Math.floor((t+(period - deadline))/period)*period));
		return Math.floor((t+(period-deadline))/period)*exe + CI_t;
		
	}
	/*
	 * Get the CarryIn workload of tau_i to tau_k
	 * Equation 3 of Arvind's paper in 09: CI_{i}(t)
	 */
	public double getCI(double t){
		return Math.min(exe, Math.max(0, t - Math.floor((t+(period - deadline))/period)*period));
	}
	
	
	public Task(){
		
	}
	
	public Task(String name, String period, String deadline, String exe){
		this.name = name;
		this.period = Double.parseDouble(period);
		this.deadline = Double.parseDouble(deadline);
		this.exe = Double.parseDouble(exe);
	}
	
	
	public Task(String name, String period, String deadline, String exe, 
			String delta_rel, String delta_sch, String delta_cxs, String delta_crpmd){
		this.name = name;
		this.period = Double.parseDouble(period);
		this.deadline = Double.parseDouble(deadline);
		this.exe = Double.parseDouble(exe);
		this.delta_rel = Double.parseDouble(delta_rel);
		this.delta_sch = Double.parseDouble(delta_sch);
		this.delta_cxs = Double.parseDouble(delta_cxs);
		this.delta_crpmd = Double.parseDouble(delta_crpmd);
	}
	
	public Task(double period, double exe, double deadline){
		if(exe > deadline){
			System.err.println("\r\nATTENTION: task's execution > deadline!\r\n");
		}
		if(exe == deadline){
			Tool.debug("\r\nATTENTION: task's execution == deadline!\r\n");
		}
		this.name = "default";
		this.period = period;
		this.deadline = deadline;
		this.exe = exe;
		this.delta_rel = 0;
		this.delta_sch = 0;
		this.delta_cxs = 0;
		this.delta_crpmd = 0;
	}
	
	public Task(String period, String deadline, String exe){
		this.period = Double.parseDouble(period);
		this.deadline = Double.parseDouble(deadline);
		this.exe = Double.parseDouble(exe);
		this.delta_rel = 0;
		this.delta_sch = 0;
		this.delta_cxs = 0;
		this.delta_crpmd = 0;
	}
	
	/*
	 * private double period;
	private double exe;
	private double deadline;
	private double delta_rel;	// release overhead
	private double delta_sch;	// schedule overhead
	private double delta_crpmd;	// cache related preemption/migration overhead
	private double delta_cxs;	// context swtich overhead
	private String name;(non-Javadoc)
	 * @see java.lang.Object#toString()
	 */
	public String toString(){
		String str = "--task--";
		str += "name:" + this.name + ", period:" + this.period + ", exe:" + this.exe + 
				", deadline:" + this.deadline + ", delta_rel:" + this.delta_rel + ", delta_sch:" + this.delta_sch + 
				", delta_cxs:" + this.delta_cxs + ", delta_crpmd:" + this.delta_crpmd + "\r\n";
		return str;
	}
	
	
	//////////Get Set function////////////////

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
