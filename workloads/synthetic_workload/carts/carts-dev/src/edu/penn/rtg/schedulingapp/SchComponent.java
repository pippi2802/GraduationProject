package edu.penn.rtg.schedulingapp;

@SuppressWarnings("serial")
public class SchComponent{
	// basic info
	protected double minPeriod;
	protected double maxPeriod;
	protected double period = 0; // meng period = minPeriod, when minPeriod = maxPeriod. Used in MPR, DMPR, CADMPR
	protected String algorithm;		// Local Scheduling Algorithm within component (EDF/RM)
	// optional info
	protected String vmips = "";
	protected String subType = "";
	protected String criticality = "";
	
	// internal info
	protected boolean revised = false;
	protected String processedAlgo=new String();
	protected TreeComponent tree_com;

	public SchComponent(TreeComponent tree_com) {
		this.tree_com = tree_com;
	}

	/////////////////////////////////////
	// Get Set
	/////////////////////////////////////




	// maximum period

	public void setMaxPeriod(double max)
	{
		this.maxPeriod=max;
	}

	/**
	 * Return maximum period of resource model of component
	 * 
	 * @return maximum period
	 */

	public double getMaxPeriod() {
		return maxPeriod;
	}

	// minimum period

	public void setMinPeriod(double min)
	{
		this.minPeriod=min;
	}

	/**
	 * Return minimum period of resource model of component
	 * 
	 * @return minimum period
	 */

	public double getMinPeriod() {
		return minPeriod;
	}


	// algorithm 

	public double getPeriod() {
		return period;
	}

	public void setPeriod(double period) {
		this.period = period;
	}

	/**
	 * Set scheduling algorithm (EDF,DM)
	 * @param alg scheduling algorithm (EDF,DM)
	 */

	public void setAlgorithm(String alg) {
		algorithm = alg;
	}

	/**
	 * Get scheduling algorithm (EDF,DM)
	 * @return scheduling algorithm (EDF,DM)
	 */

	public String getAlgorithm() {
		return algorithm;
	}

	public void setVmipsStr(String vmipsStr) {
		vmips = vmipsStr;
	}
	
	public String getVmipsStr() {
		return vmips;
	}
	
	public void setSubType(String subType) {
		this.subType = subType;
	}
	
	public String getSubType() {
		return subType;
	}
	
	public void setCriticality(String criticality) {
		this.criticality = criticality;
	}
	
	public String getCriticality() {
		return criticality;
	}

	/**
	 * Update the component field with new values
	 * 
	 * @param c
	 *            SchedulingComponent
	 */
	public boolean update(SchComponent c)
	{
		boolean isUpdated=false;
		if(!this.algorithm.equals(c.algorithm)) {
			setAlgorithm(c.algorithm);
			isUpdated=true;
		}
		if(this.minPeriod!=c.minPeriod) {
			setMinPeriod(c.minPeriod);
			isUpdated=true;
		}
		if(this.maxPeriod!=c.maxPeriod) {
			setMaxPeriod(c.maxPeriod);
			isUpdated=true;
		}
			
		setMinPeriod(c.minPeriod);
		setMaxPeriod(c.maxPeriod);
		setSubType(c.subType);
		setVmipsStr(c.vmips);
		setCriticality(c.criticality);
		return isUpdated;
	}



	/**
	 * Is local scheduler EDF
	 * 
	 */
	public boolean isEDF()
	{
		//System.out.println(algorithm);
		if (algorithm.equalsIgnoreCase("edf") || algorithm.equalsIgnoreCase("pEDF")) return true;
		else return false;
	}
	/**
	 * Is local scheduler EDF
	 * 
	 */

	public boolean isDM()
	{
		if (algorithm.equalsIgnoreCase("dm") || algorithm.equalsIgnoreCase("pDM")) return true;
		else if (algorithm.equalsIgnoreCase("rm") || algorithm.equalsIgnoreCase("pRM")) return true;
		else return false;
	}





	public boolean isRevised() {
		return revised;
	}

	public void setRevised(boolean revised) {
		this.revised = revised;
	}

	public void setProcAlgoRecur(String algo) {
		for (TreeComponent child : tree_com.getAllChildren()) {
			SchComponent sc=child.getSchCom();
			sc.setProcAlgoRecur(algo);
		}
		processedAlgo=algo;
		
	}
	public String getProcessedAlgo()
	{
		return processedAlgo;
	}
	public void printDebug()
	{
		//System.out.println(compName);
		System.out.println(algorithm);
		System.out.println(maxPeriod);
		System.out.println(minPeriod);
	}
	public void printInside()
	{
		for (TreeComponent child : tree_com.getAllChildren()) {
			SchComponent sc=child.getSchCom();
			sc.printInside();
		}
		printDebug();
		for(Task t:tree_com.getTaskList().getTasks()){
			t.printDebug();
		}
	}
	/**
	 * Writes the component's details into the buffer. Recursively calls the
	 * descendants to write their details
	 * 
	 * @param buffer
	 */
	public void convertToXML(StringBuffer buffer) {
		if (tree_com.getParentComp() == null) {
			buffer.append("<system os_scheduler=\"" + algorithm + "\"");
			buffer.append("	min_period=\"" + ((int) minPeriod) + "\"");
			buffer.append("	max_period=\"" + ((int) maxPeriod) + "\">\n");

			for (TreeComponent child : tree_com.getAllChildren()) {
				SchComponent sc=child.getSchCom();
				sc.convertToXML(buffer);
			}
			tree_com.getTaskList().convertToXML(buffer);
			buffer.append("</system>\n");
		} else {
			buffer.append("<component");
			buffer.append(" name=\"" + tree_com.getCompName() + "\"");
			buffer.append("	scheduler=\"" + algorithm + "\"");
			buffer.append("	min_period=\"" + ((int) minPeriod) + "\"");
			buffer.append("	max_period=\"" + ((int) maxPeriod) + "\"");
			if(!vmips.equals("")){
				buffer.append("	vmips=\"" + vmips + "\"");
			}
			if(!criticality.equals("")){
				buffer.append(" criticality=\"" + criticality + "\"");
			}
			if(!subType.equals("")){
				buffer.append("	subtype=\"" + subType + "\"");
			}
			buffer.append(">\n");

			tree_com.getTaskList().convertToXML(buffer);
			for (TreeComponent child : tree_com.getAllChildren()) {
				SchComponent sc=child.getSchCom();
				sc.convertToXML(buffer);
			}

			buffer.append("</component>\n");
		}
	}

}
