package edu.penn.rtg.schedulingapp;

import java.io.PrintStream;
import java.text.DecimalFormat;

import edu.penn.rtg.schedulingapp.basic.EqvPrmModel;
import edu.penn.rtg.schedulingapp.basic.IntPRM;
import edu.penn.rtg.schedulingapp.basic.ResModel;
/**
 * Resource Model. <P>
 * Resource Model characterize a partitioned resource that guarantees allocations of \Theta time units every \Pi time units.
 * If we can abstract component as a single task with execution time \Theta and period \Pi, 
 * we can transform it to a resource model with ( \Pi , \Theta)
 * <P>
 * Support Period as Integer, Deadline and Execution as Double
 * @author      Jaewoo Lee, Meng Xu
 * @version     1.1
 * @since       1.0
 */
public class ResourceModel {

	private int Period;
	private double Bandwidth; // Bandwidth = Execution/Period
	private double Deadline;
	private DecimalFormat df=new DecimalFormat("#.####");
	public double period2; //MPR's period
	public double exec2; //MPR's Theta
	public int cpus;
	public int type=0;
	public String notes;
	public static final int PRM=0;
	public static final int DPRM=1;
	public static final int MPR=2;
	public static final int EQV=3;
	public static final int DMPR = 4;
	public static final int CADMPR_TASKCENTRIC = 5;
	public static final int CADMPR_MODELCENTRIC = 6;
	public static final int CADMPR_HYBRID = 7;
	
	//------------------- These two fields are added by SC, with separate setter methods --------//
	//------------------- No change to other part of this class ---------------------------------//
	public IntPRM initRes = new IntPRM(0,0);
	public EqvPrmModel eqvRes = new EqvPrmModel();

	public void setInitRes(IntPRM initRes){
		this.initRes = initRes;
	}

	public void setEqvRes(EqvPrmModel eqvRes){
		this.eqvRes = eqvRes;
	}
	//-------------------------------------------------------------------------------------------//
		
	/**
	 * Resource Model Constructor, set period, bandwidth, and deadline
	 * 
	 * @param period period of resource model 
	 * @param bandwidth bandwidth of resource model 
	 * @param deadline deadline of resource model 
	 */
	public ResourceModel(int period, double bandwidth, double deadline) {
		// System.err.println("======== " + period + " " + bandwidth + " "
		// + deadline);
		this.Period = period;
		this.Bandwidth = bandwidth;
		this.Deadline = deadline;
	}
	
	public ResourceModel(double Pi, double Theta, int m_prime, int period, double bandwidth, double deadline){
		this.period2 = Pi;
		this.exec2 = Theta;
		this.cpus = m_prime;
		this.Period = period;
		this.Bandwidth = bandwidth;
		this.Deadline = deadline;
	}
	/**
	 * Return period of resource model 
	 * @return      period of resource model 
	 */

	public int getPeriod() {
		return this.Period;
	}

	/**
	 * Return bandwidth of resource model 
	 * @return      bandwidth of resource model 
	 */

	public double getBandwidth() {
		return this.Bandwidth;
	}

	/**
	 * Return deadline of resource model 
	 * @return      deadline of resource model 
	 */

	public double getDeadline() {
		return this.Deadline;
	}
	/**
	 * It compute Supply Bound Function of resource model 
	 * 
	 * @param time given time
	 * @return      Supply Bound Function of resource model 
	 */

	public double computeSBF(double time) {
		double exec=this.Bandwidth * this.Period;
		if(time<this.Period-exec) return 0;
		double floor = Math.floor((time - (this.Deadline - exec))/ this.Period);
		double mod=time-floor*this.Period; //residual
		double plus=Math.max(0,mod-(this.Period+this.Deadline-2*exec));
		double supply = floor*exec+plus;
		return supply;
		/*
		double theta = this.Bandwidth * this.Period;
		if (time > this.Period - theta) {

			double floor = Math.floor((time - (this.Deadline - theta))
					/ this.Period);
			return floor
					* theta
					+ Math.max(0, time
							- (this.Period + this.Deadline - 2 * theta) - floor
							* this.Period);
		} else
			return 0;
		*/
	}

	public double computeLowerSBF(double time) {
		double theta = this.Bandwidth * this.Period;
		if (time > this.Period - theta) {

			/*
			 * return floor theta + (time -(this.Deadline - theta) - floor
			 * this.Period)theta;
			 */
			return (time - (this.Deadline - theta)) * this.Bandwidth;
		} else
			return 0;
	}

	/**
	 * It compute Lower Supply Bound Function of resource model (for schedulability test)
	 * 
	 * @param time given time
	 * @return      Supply Bound Function of resource model 
	 */

	public double computeLSBF(double time) {
		return this.Bandwidth
				* (time - (this.Period + this.Deadline - 2 * (this.Bandwidth * this.Period)));
	}

	/**
	 * It write debug message to command line
	 * 
	 * @return      none
	 */
	public void printDPRM() {
		System.out.print((int)(Period) + " " +(int)(Bandwidth)+" ");
		System.out.println(period2 + " " +(exec2));
	}
	

	/**
	 * It write debug message to command line
	 * 
	 * @return      none
	 */
	public void print() {


		double period = this.getPeriod();
		double bandwidth = this.getBandwidth();
		double deadline = this.getDeadline();
		bandwidth = bandwidth * 10000;
		bandwidth = (double) Math.round(bandwidth);
		bandwidth = bandwidth / 10000;
		period = period * 10000;
		period = (double) Math.round(period);
		period = period / 10000;
		deadline = deadline * 10000;
		deadline = (double) Math.round(deadline);
		deadline = deadline / 10000;
		//System.out.println(speriod + " " + sbandwidth + " " + sdeadline);
	}
	/**
	 * It write debug message to file
	 * 
	 * @param out	file's outputsteam
	 */

	public void printFile(PrintStream out) {

		int period = this.getPeriod();
		double bandwidth = this.getBandwidth();
		double deadline = this.getDeadline();
//		bandwidth = bandwidth * 10000;
//		bandwidth = (double) Math.round(bandwidth);
//		bandwidth = bandwidth / 10000;
		String sbandwidth = (new Double(df.format(bandwidth))).toString();
//		period = period * 10000;
//		period = (double) Math.round(period);
//		period = period / 10000;
		String speriod = (new Integer(period)).toString();
//		deadline = deadline * 10000;
//		deadline = (double) Math.round(deadline);
//		deadline = deadline / 10000;
		String sdeadline = (new Double(deadline)).toString();
		out.println(speriod + " " + sbandwidth + " " + sdeadline);
	}

	/**
	 * It write Resource Model's message to string
	 * 
	 */

	@Override
	public String toString() {
		String retString = new String();
		if(type==PRM) {
			retString += "Period: ";
			retString+=df.format(getPeriod());
			retString += ", Bandwidth: ";
			retString+=df.format(getBandwidth());
			retString += ", Deadline: ";
			retString+=df.format(getDeadline());
		} else if(type==DPRM) {
			retString += "Period: ";
			retString+=(int)(getPeriod());
			retString += ", Execution Time: ";
			retString+=(int)(getBandwidth());
		} else if(type==MPR) {
			if(period2 != 0 && exec2 != 0 && cpus != 0){
				retString += ", Period: ";
				retString+=df.format(period2);
				retString += ", Execution Time: ";
				retString+=df.format(exec2);	
				retString += ", Cpus: ";
				retString+=cpus;
			}
			
		} else if(type==DMPR) {
			if(period2 != 0 && (exec2 != 0 || cpus != 0)){
				retString += "Pi: ";
				retString+=df.format(period2);
				retString += ", Theta: ";
				retString+=df.format(exec2);
				retString += ", m': ";
				retString+=cpus;	
			}
					
		} else if(type==CADMPR_TASKCENTRIC) {
			if(period2 != 0 && (exec2 != 0 || cpus != 0)){
				retString += "Pi: ";
				retString+=df.format(period2);
				retString += ", Theta: ";
				retString+=df.format(exec2);
				retString += ", m': ";
				retString+=cpus;
			}
		} else if(type==CADMPR_MODELCENTRIC) {
			if(period2 != 0 && (exec2 != 0 || cpus != 0)){
				retString += "Pi: ";
				retString+=df.format(period2);
				retString += ", Theta: ";
				retString+=df.format(exec2);
				retString += ", m': ";
				retString+=cpus;
			}
		} else if(type==CADMPR_HYBRID) {
			if(period2 != 0 && (exec2 != 0 || cpus != 0)){
				retString += "Pi: ";
				retString+=df.format(period2);
				retString += ", Theta: ";
				retString+=df.format(exec2);
				retString += ", m': ";
				retString+=cpus;
			}
		} else if(type==EQV) {
			retString += "Final Model: ";
			retString += "Period: ";
			retString+=(int)(getPeriod());
			retString += ", Execution Time: ";
			retString+=df.format(getBandwidth());
			retString += ", Deadline: ";
			retString+=df.format(getDeadline());
			retString += ", Bandwidth: ";
			retString+=df.format((double)getBandwidth()/getPeriod());						
			if(this.initRes.getPeriod() > 0){
				retString += "\n";
				retString += "Initial Model: ";
				retString += "Period: ";
				retString+=(int)(this.initRes.getPeriod());

				retString += ", Execution Time: ";
				retString+=df.format(this.initRes.getExe());
				retString += ", Deadline: ";
				retString+=df.format(this.initRes.getPeriod());
				retString += ", Bandwidth: ";
				retString+=df.format((double)this.initRes.getExe()/this.initRes.getPeriod());
			}			
			if(this.eqvRes.periodSet.contBound > 0){
				retString += "\n";
				retString += "Equivalent Periods-Bandwidth Model: ";
				retString += ", Bandwidth: ";
                                retString +=df.format(this.eqvRes.bandwidth);
                                retString += ", Half continuous period bound: ";
                                retString += df.format(this.eqvRes.periodSet.contBound);
				retString += ", Discrete candidate periods: ";
				for(int i = 0; i <= this.eqvRes.periodSet.discSet.size() - 1; i++) {
				    retString += (int)(this.eqvRes.periodSet.discSet.get(i));
				    retString += " , ";
				}				
			}
		}


		return retString;
	}

	/**
	 * It write debug message to string by calling toString()
	 * 
	 */

	public String getResult() {
		return toString();
	}
	public double computeSBF_Arinc(double time) {
		double exec=this.Bandwidth * this.Period;
		if(time<this.Period-exec) return 0;
		double floor = Math.floor(time/ this.Period);
		double mod=time-floor*this.Period; //residual
		double plus=Math.max(0,mod-(this.Period-exec));
		double supply = floor*exec+plus;
		return supply;
	}
	public int computeSBF_DPRM(int t) {
		return getSupply(t,(int)Period,(int)Bandwidth)+getSupply(t,period2,exec2);
	}

	private int getSupply(int t, double period, double exec) {
		int y=(int) Math.floor((t-(period-exec))/period);
		int x= (int) (2*(period-exec));
		int rem=(int)Math.max(0,t-x-y*period);
		int s=(int) (Math.floor(y*exec)+rem);
		s=Math.max(0,s);

		return s;
	}

	public int getType() {
		return type;
	}

	public void setType(int type) {
		this.type = type;
	}

	/*
	 * public static final int PRM=0;
	public static final int DPRM=1;
	public static final int MPR=2;
	public static final int EQV=3;
	public static final int DMPR = 4;
	public static final int CADMPR_TASKCENTRIC = 5;
	public static final int CADMPR_MODELCENTRIC = 6;
	public static final int CADMPR_HYBRID = 7;
	
	 */
	public void setType(String modelType){
		if(modelType.equals("PRM"))
			this.type = ResourceModel.PRM;
		if(modelType.equals("DPRM"))
			this.type = ResourceModel.DPRM;
		if(modelType.equals("MPR"))
			this.type = ResourceModel.MPR;
		if(modelType.equals("EQV"))
			this.type = ResourceModel.EQV;
		if(modelType.equals("DMPR"))
			this.type = ResourceModel.DMPR;
		if(modelType.equals("CADMPR_TASKCENTRIC"))
			this.type = ResourceModel.CADMPR_TASKCENTRIC;
		if(modelType.equals("CADMPR_MODELCENTRIC"))
			this.type = ResourceModel.CADMPR_MODELCENTRIC;
		if(modelType.equals("CADMPR_HYBRID"))
			this.type = ResourceModel.CADMPR_HYBRID;
		
	}
	
}
