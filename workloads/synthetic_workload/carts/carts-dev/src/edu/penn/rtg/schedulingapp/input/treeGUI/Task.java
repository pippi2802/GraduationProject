package edu.penn.rtg.schedulingapp.input.treeGUI;

import javax.swing.tree.DefaultMutableTreeNode;
import java.text.DecimalFormat;

/**
 * Task class represents the tasks present in a Scheduling Component. The class
 * contains fields for Task Period, Execution Period, Task Deadline.
 */
@SuppressWarnings("serial")
public class Task extends DefaultMutableTreeNode {
	/**
	 * Jitter and Non Interrupt Function have been commented out as they are
	 * presently used for analysis
	 */
	private DecimalFormat df=new DecimalFormat("#.####");
	private String name;
	private double period;
	private double execution;
	private double deadline;
	private double criticalSection; // Critical Section Length
	private double jitter;
	private double offset;
	private double m_nonIntFunc;
	//===overhead===//
	private double delta_rel;
	private double delta_sch;
	private double delta_cxs;
	private double delta_crpmd;

	public Task(String name)
	{
		super(name);
		this.name=name;
	}
	public Task(Task task)
	{
		update(task);
	}
	public Task(double period, double execution, double deadline)
	{
		this.period=period;
		this.execution=execution;
		this.deadline=deadline;
	}
	
	public Task(String name, double period, double execution,
			double deadline, double delta_rel, double delta_sch,
			double delta_cxs, double delta_crpmd) {
		super();
		this.name = name;
		this.period = period;
		this.execution = execution;
		this.deadline = deadline;
		this.delta_rel = delta_rel;
		this.delta_sch = delta_sch;
		this.delta_cxs = delta_cxs;
		this.delta_crpmd = delta_crpmd;
	}
	
	
	public Task(String name, double period, double execution,
			double deadline, double delta_crpmd) {
		super();
		this.name = name;
		this.period = period;
		this.execution = execution;
		this.deadline = deadline;
		this.delta_crpmd = delta_crpmd;
	}
	
	
	
	public Task(String name, double period,
			double execution, double deadline, double criticalSection,
			double jitter, double offset, double m_nonIntFunc,
			double delta_rel, double delta_sch, double delta_cxs,
			double delta_crpmd) {
		super();
		this.name = name;
		this.period = period;
		this.execution = execution;
		this.deadline = deadline;
		this.criticalSection = criticalSection;
		this.jitter = jitter;
		this.offset = offset;
		this.m_nonIntFunc = m_nonIntFunc;
		this.delta_rel = delta_rel;
		this.delta_sch = delta_sch;
		this.delta_cxs = delta_cxs;
		this.delta_crpmd = delta_crpmd;
	}
	
	public boolean update(Task task)
	{
		boolean isUpdated=false;
		if(task.name!=null) setTaskName(task.name);
		if(this.period!=task.period) {
			this.period=task.period;
			isUpdated=true;
		}
		if(this.execution!=task.execution) {
			this.execution=task.execution;
			isUpdated=true;
		}
		if(this.deadline!=task.deadline) {
			this.deadline=task.deadline;
			isUpdated=true;
		}
		if(this.criticalSection!=task.criticalSection) {
			this.criticalSection=task.criticalSection;
			isUpdated=true;
		}
		if(this.jitter!=task.jitter) {
			this.jitter=task.jitter;
			isUpdated=true;
		}
		if(this.offset!=task.offset) {
			this.offset=task.offset;
			isUpdated=true;
		}
		return isUpdated;
	}

	/**
	 * @deprecated should change to different function which convert to different XML structure
	 * Writes the Task fields into the given buffer
	 */
	public void convertToXML(StringBuffer buffer) {
		buffer.append("<task");
		buffer.append(" name=\"" + name + "\"");
		buffer.append(" p=\"" + (int) period + "\"");
		buffer.append(" d=\"" + (int) deadline + "\"");
		buffer.append(" e=\"" + execution + "\"");
		if(criticalSection!=0)
		{
			buffer.append(" cs=\"" + (int) criticalSection + "\"");
		}
		if(jitter!=0)
		{
			buffer.append(" jitter=\"" + (int)jitter + "\"");
		}
		if(offset!=0)
		{
			buffer.append(" offset=\"" + (int)offset + "\"");
		}
		if(m_nonIntFunc!=0)
		{
			buffer.append(" noninterrupt_fraction=\"" + (int) m_nonIntFunc + "\"");
		}
		buffer.append("></task>\n");
	}

	public void printDebug()
	{
		System.out.println("name: " + name);
		System.out.println("period: " + period);
		System.out.println("exe: " + execution);
		System.out.println("deadline: " + deadline);
		System.out.println("cs: " + criticalSection);
		System.out.println("jitter: " + jitter);
		System.out.println("offset: " + offset);
		System.out.println("m_nonIntFunc: " + m_nonIntFunc);
		System.out.println("delta_rel: " + this.delta_rel);
		System.out.println("delta_sch: " + this.delta_sch);
		System.out.println("delta_cxs: " + this.delta_cxs);
		System.out.println("delta_crpmd: " + this.delta_crpmd);
	}
	public void print()
	{
		System.out.println(period+" "+execution);
	}

	/**
	 * Returns the result of the Algorithm Analysis in a String
	 * 
	 * @return
	 */
	public String getResult() {
		String  retString = new String();

		retString += "Period: ";
		retString+=df.format(period);
		
		retString += ", Execution Time: ";
		retString+=df.format(execution);

		retString += ", Deadline: ";
		retString+=df.format(deadline);

		return retString;
	}

	/**
	 * Returns the name of the Task
	 * 
	 * @return
	 */
	public String getTaskName() {
		return name;
	}

	/**
	 * Sets the name of the Task
	 * 
	 * @param name
	 */
	public void setTaskName(String name) {
		setUserObject(name);
		this.name = new String(name);
	}

	/**
	 * Returns the period of the Task
	 * 
	 * @return
	 */
	public double getPeriod() {
		return period;
	}

	/**
	 * Sets the period of the Task
	 * 
	 * @param period
	 */
	public void setPeriod(double period) {
		this.period = period;
	}

	/**
	 * Returns the execution time of the Task
	 * 
	 * @return
	 */
	public double getExecution() {
		return execution;
	}

	/**
	 * Sets the execution time of the task
	 * 
	 * @param executionTime
	 */
	public void setExecution(double execution) {
		this.execution = execution;
	}

	/**
	 * Returns the deadline of the Task
	 * 
	 * @return
	 */
	public double getDeadline() {
		return deadline;
	}

	/**
	 * Sets the deadline of the Task
	 * 
	 * @param deadline
	 */
	public void setDeadline(double deadline) {
		this.deadline = deadline;
	}

	/**
	 * Returns the length of critical section
	 * 
	 * @return
	 */
	public double getCriticalSection() {
		return criticalSection;
	}

	/**
	 * Sets the length of critical section
	 * 
	 * @param critical_section
	 */
	public void setCriticalSection(double criticalSection) {
		this.criticalSection = criticalSection;
	}


	public void setJitter(double j) {
		jitter = j;
	}
	
	public double getJitter() {
		return jitter;
	}

	public void setOffset(double o) {
		offset = o;
	}
	
	public double getOffset() {
		return offset;
	}
	
	public void setNonIntFunc(double nonIntFunc) {
		m_nonIntFunc = nonIntFunc;
	}
	
	public double getNonIntFunc() {
		return m_nonIntFunc;
	}
	public String getName() {
		return name;
	}
	public void setName(String name) {
		this.name = name;
	}
	public double getM_nonIntFunc() {
		return m_nonIntFunc;
	}
	public void setM_nonIntFunc(double m_nonIntFunc) {
		this.m_nonIntFunc = m_nonIntFunc;
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
	public double getDelta_cxs() {
		return delta_cxs;
	}
	public void setDelta_cxs(double delta_cxs) {
		this.delta_cxs = delta_cxs;
	}
	public double getDelta_crpmd() {
		return delta_crpmd;
	}
	public void setDelta_crpmd(double delta_crpmd) {
		this.delta_crpmd = delta_crpmd;
	}
	
	

}
