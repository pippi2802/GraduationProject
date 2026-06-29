package edu.penn.rtg.schedulingapp.algo;


import java.util.Vector;

import edu.penn.rtg.common.GlobalVariable;
import edu.penn.rtg.schedulingapp.ResourceModel;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.util.SchException;
import edu.penn.rtg.schedulingapp.util.UserUtil;
/**
 * Compute optimal bandwidth and deadline (EDF, Periodic).
 * this class has two main function<P>
 * 1. Compute optimal bandwidth <BR>
 * Using schedulability test, it compute optimal bandwidth <P>
 * 2. transform a resource model  into a single task<P>
 * supported resource model : Periodic Resource Model <BR>
 * supported scheduling algorithm : EDF
 * <P>
 * @author      
 * @version     1.0
 * @since       1.0
 */
public class EDFSchedulability_periodic {

	private int resPeriod;
	private SchedulingComponent C;
	/**
	 * Constructor
	 * It set target component and target period
	 * @param  C	target component
	 * @param  period given period
	 */
	public EDFSchedulability_periodic(SchedulingComponent C, int resPeriod)
			throws Exception {

		if (!C.isEDF()) {
			UserUtil.show("The component has algorithm set to DM. Cannot continue");
			throw new SchException();
		}
		this.resPeriod = resPeriod;
		this.C = C;
	}
	
	/**
	 * Meng's implementation of calculating an Interface's bandwidth for a given period
	 * @return
	 */
	public double getBandwidth_mengImpl(){
		int Pi = resPeriod;
		double minBandwidth = 100 * resPeriod;
		double L = C.computeLCM(resPeriod);	
		
		if(2*L >= GlobalVariable.MAX_NUMBER || L < 0){ //if lcm is too large to computable, return minBandwidth = 2.1 which is unschedualb.e
			return GlobalVariable.BANDWIDTH_VALUE_UNSCHED;
		}

		for(double currTheta = 0; true; currTheta += GlobalVariable.TIME_PRECISION){
			boolean isCurrThetaSched = true;
			for(double t = 0; t <= 2*L; t += GlobalVariable.TIME_PRECISION){
				double dbf_t = 0, sbf_t = 0;
				Vector<Task> taskset =  this.C.getTasks(resPeriod); //DeadlineAscending sorted tasks
				//calculate demand of taskset
				for(int index = 0; index<taskset.size(); index++){
					Task currTask = taskset.get(index);
					dbf_t += Math.max(0, 
							Math.floor( (t+currTask.getPeriod() - currTask.getDeadline())/currTask.getPeriod() ) ) * currTask.getExecution();
				}				
				//calculate resource of the interface
				if(t < Pi - currTheta){
					sbf_t = 0;
				}else{
					sbf_t = Math.floor( (t - (Pi - currTheta) ) / Pi ) * currTheta
							+ Math.max(0, t - 2*(Pi - currTheta) - Math.floor( (t - (Pi-currTheta) )/Pi )*Pi);
				}
				if(dbf_t > sbf_t){
					isCurrThetaSched = false;
					break;
				}
				
			}
			if(isCurrThetaSched == true){ //this is the first Theta that's schedulable
				minBandwidth = currTheta * 1.0 / Pi;
				break;//return the min bandwidth
			}
			
			if(GlobalVariable.FAST_PATH == true 
					&& currTheta*1.0/Pi > GlobalVariable.BANDWIDTH_THRESHOLD_UNSCHED){
				minBandwidth = GlobalVariable.BANDWIDTH_VALUE_UNSCHED; //speed up the calculation when the task set is already claimed schedulable.
				break;
			}
		}
		return minBandwidth;
	}
	
	
	/**
	 * It calculates optimal bandwidth of given component and given period
	 * by using schedulability test. 
	 *
	 * @return      optimal bandwidth.
	 * @see         none
	 */
	public double getBandwidth() {
		
		if(GlobalVariable.IMPL_METHOD != GlobalVariable.JAEWOO_IMPL){
			return getBandwidth_mengImpl();
		}

		double time = 0, tprime = 0, tprime0 = 0, tprime1 = 0;
		double lcm = C.computeLCM(resPeriod);
		double olddemand = 0;
		double minBandwidth = 0;
		double bandwidth = 0;
		int k = 0;
		double alpha = 0, delta = 0;
		double s0 = 0, s1 = -1, f0 = 0, f1 = 0;

		double theta = 0, theta1, theta2, thetaOpt;
		if (lcm > 20000) {
			lcm = C.computeLCM(resPeriod);
		}
		while (time <= 2*lcm) {
			time = time + 1;
			double demand = C.computeDBF(time, resPeriod);
			if (demand == olddemand)
				continue;
			olddemand = demand;
			//System.out.println(time+"," + demand);

			k = (int) Math.floor(time / this.resPeriod);
			alpha = time - k * this.resPeriod;

			delta = this.resPeriod;
			theta = 0;
			f0 = Math.floor((alpha - delta + theta) / this.resPeriod);
			tprime0 = f0 * this.resPeriod + k * this.resPeriod;
			s0 = (theta / this.resPeriod) * (tprime0 - (delta - theta));
			// tprime should not be negative ( 2010.1.27 : Jaewoo Lee)
			tprime0 = Math.max(0,tprime0);

			if (f0 == -1) {
				theta = delta - alpha;
				f1 = Math.floor((alpha - delta + theta) / this.resPeriod);
				tprime1 = f1 * this.resPeriod + k * this.resPeriod;
				// tprime should not be negative ( 2010.1.27 : Jaewoo Lee)
				tprime1 = Math.max(0,tprime1);

				s1 = (theta / this.resPeriod) * (tprime1 - (delta - theta));

			}
			//System.out.println("S:"+s1+","+s0+","+demand);
			/*
			if( s1< 0) 
			{
				minBandwidth=0;
				break;
			}
			*/
			if ((s1 > s0) && (s1 <= demand))
				tprime = tprime1;
			else
				tprime = tprime0;

			theta1 = demand * this.resPeriod / tprime;
			theta2 = (demand + tprime + 2 * this.resPeriod - time)
					* this.resPeriod / (tprime + 2 * this.resPeriod);
			thetaOpt = Math.min(Math.max(theta1, 0), Math.max(theta2, 0));
			bandwidth = thetaOpt / this.resPeriod;

			// */
			//System.out.println("min:"+thetaOpt/this.resPeriod+","+theta1+","+theta2);
			minBandwidth = Math.max(minBandwidth, bandwidth);

		}
		 //System.out.println(minBandwidth);
		return minBandwidth;
	}

	/**
	 * Depending on the scheduling algorithm employed by object c, it transform 
	 * given resource model into a task with given period(periodic resource model). 
	 * @param  edp target resource model
	 * @param  period given period
	 * @return      A Task characterizing a periodic task with given period.
	 * @see         Task
	 */
	Task T_EDF(ResourceModel edp) {
		return (new Task(edp.getPeriod(), edp.getBandwidth() * edp.getPeriod(),
				edp.getPeriod()));
	}

}
