package edu.penn.rtg.schedulingapp.algo;

import java.util.Vector;

import edu.penn.rtg.schedulingapp.ResourceModel;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.util.SchException;
import edu.penn.rtg.schedulingapp.util.UserUtil;
/**
 * Compute optimal bandwidth and deadline (DM, Periodic).
 * this class has two main function<P>
 * 1. Compute optimal bandwidth <BR>
 * Using schedulability test, it compute optimal bandwidth <P>
 * 2. transform a resource model  into a single task<P>
 * supported resource model : Periodic Resource Model  <BR>
 * supported scheduling algorithm : DM
 * <P>
 * @author      
 * @version     1.0
 * @since       1.0
 */
public class DMSchedulability_sirap {

	private int givenPeriod;
	private int resPeriod;
	private SchedulingComponent comp;
	/**
	 * Constructor
	 * It set target component and target period
	 * @param  period given period
	 * @param  C	target component
	 */
	public DMSchedulability_sirap(SchedulingComponent C, int givenPeriod)
			throws Exception {
		if (!C.isDM()) {
			UserUtil.show("The component has algorithm set to EDF. Cannot continue");
			throw new SchException();
		}
		this.comp=C;
		this.givenPeriod = givenPeriod;
		resPeriod=givenPeriod;
	}
	public double getNewBandwidth()
	{
		Vector<Task> taskV=comp.getTasks(givenPeriod);
		double max_bandwidth=0;
		for(int i=0;i<taskV.size();i++)
		{
			Task task=(Task)taskV.get(i);
			double period=task.getPeriod();
			double demand=getRBF_SIRAP(i,period,givenPeriod);
			double bandwidth=demand/period;
			if(max_bandwidth<bandwidth) max_bandwidth=bandwidth;
			//System.out.println(i+","+demand+","+period);
			//System.out.println(i+","+bandwidth+","+max_bandwidth);

		}
		return max_bandwidth;
	}
	/**
	 * It calculates optimal bandwidth of given component and given period
	 * by using schedulability test. 
	 *
	 * @return      optimal bandwidth.
	 * @see         none
	 */


	public double getBandwidth() {
		double minBandwidth = 0;
		double time = 0, tprime = 0, tprime0 = 0, tprime1 = 0;
		//double lcm = comp.computeLCM(resPeriod);
		double olddemand = 0;
		int k = 0;
		double alpha = 0, delta = 0;
		double s0 = 0, s1 = -1, f0 = 0, f1 = 0;

		double theta = 0, theta1, theta2, thetaOpt = 0;
		double bandwidth = 0;
		//System.out.println("Comp:" + C.getCompName());
		for (int index = 0; index < this.comp.getSize(resPeriod); index++) {

			double period = this.comp.getTasks(resPeriod).get(index).getPeriod();
			double exec = this.comp.getTasks(resPeriod).get(index).getExecution();
			if(exec<=0) continue;
			time = period;
			double taskBandwidth = 100;
			olddemand = 0;
			while (time > 0) {

				double demand = getRBF_SIRAP(index,time, resPeriod);
				if (demand == olddemand) {
					time = time - 1;
					continue;
				}
				olddemand = demand;

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
				if (taskBandwidth > bandwidth) {

					taskBandwidth = bandwidth;
				}
				time = time - 1;
			}
			// /*
			if (minBandwidth < taskBandwidth) {

				minBandwidth = taskBandwidth;
			}

		}
		// if(this.resPeriod == 10)
		// System.out.println((new Double(this.resPeriod)).toString() + " " +
		// (new Double(minBandwidth)).toString());
		//System.out.println("min:" + minBandwidth);
		return minBandwidth;
	}


/*
	private double getRBF(int toIndex,double time)
	{
		Vector<?> taskV=comp.getTasks(givenPeriod);
		double rbf=0;
		for(int i=0;i<=toIndex;i++)
		{
			Task task=(Task)taskV.get(i);
			if(task.getPeriod()==0) continue;
			rbf+= Math.ceil(time / task.getPeriod())
						* task.getExecution();

		}
		return rbf;
	}
*/
	private double getRBF_SIRAP(int toIndex,double time,int period)
	{
		Vector<?> taskV=comp.getTasks(period);
		double rbf=0;
		for(int i=0;i<=toIndex;i++)
		{
			Task task=(Task)taskV.get(i);
			if(task.getPeriod()==0) continue;
			rbf+= Math.ceil(time / task.getPeriod())
						* (task.getExecution()+task.getCriticalSection());

		}
		double max_block=0;
		for(int i=toIndex+1;i<taskV.size();i++)
		{
			Task task=(Task)taskV.get(i);
			if(max_block<task.getCriticalSection()) max_block=task.getCriticalSection();
		}
		//System.out.println(max_block);
		return rbf+2*max_block;
	}
	

	/**
	 * Depending on the scheduling algorithm employed by object c, it transform 
	 * given resource model into a task with given period(periodic resource model). 
	 * @param  edp target resource model
	 * @param  period given period
	 * @return      A Task characterizing a periodic task with given period.
	 * @see         Task
	 */
	Task T_DM(ResourceModel edp, int period) {
		return (new Task(edp.getPeriod(), edp.getBandwidth() * edp.getPeriod(),
				edp.getPeriod()));
	}

}
