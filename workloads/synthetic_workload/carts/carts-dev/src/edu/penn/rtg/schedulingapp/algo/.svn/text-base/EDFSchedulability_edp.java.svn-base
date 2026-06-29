package edu.penn.rtg.schedulingapp.algo;

import edu.penn.rtg.schedulingapp.ResourceModel;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.util.SchException;
import edu.penn.rtg.schedulingapp.util.UserUtil;
/**
 * Compute optimal bandwidth and deadline (EDF, EDP).
 * this class has two main function<P>
 * 1. Compute optimal bandwidth and deadline <BR>
 * Using schedulability test, it compute optimal bandwidth and deadline<P>
 * 2. transform a resource model  into a single task<P>
 * supported resource model : ARINC, EDP <BR>
 * supported scheduling algorithm : EDF
 * <P>
 * @author      
 * @version     1.0
 * @since       1.0
 */
public class EDFSchedulability_edp {
	private int resPeriod;
	private SchedulingComponent C;
	/**
	 * Constructor
	 * It set target component and target period
	 * @param  period given period
	 * @param  C	target component
	 */
	public EDFSchedulability_edp(SchedulingComponent C, int resPeriod)
			throws Exception {
		if (!C.isEDF()) {
			UserUtil.show("The component has algorithm set to DM. Cannot continue");
			throw new SchException();
		}
		this.resPeriod = resPeriod;
		this.C = C;
	}
	/**
	 * It calculate optimal bandwidth of given component and given period
	 * by using schedulability test. 
	 *
	 * @return      optimal bandwidth.
	 * @see         none
	 */
	public double getBandwidth() throws Exception {
		double minBandwidth = C.computeUtil(resPeriod);
		double time = 0;
		double lcm = C.computeLCM(resPeriod);
		double maxDeadline = C.computeMaxDeadline(resPeriod);
		double oldDemand = 0;
		int k = 0;
		double theta = 0, theta1 = 0, theta2 = 0;

		while (time <= lcm + maxDeadline) {
			time = time + 1;
			double demand = C.computeDBF(time, resPeriod);
			// System.out.println(time+","+ demand);
			if (demand < oldDemand) {
				UserUtil.show("Demand Decreased");
				throw new Exception();
			}
			if (demand == oldDemand)
				continue;

			oldDemand = demand;

			k = (int) Math.floor(time / this.resPeriod);

			theta1 = demand / k;
			theta2 = (demand + (k + 1) * this.resPeriod - time) / (k + 1);
			if ((time - this.resPeriod + theta2 - k * this.resPeriod) > 0)
				theta = theta2;
			else
				theta = theta1;
			double bandwidth = theta / this.resPeriod;
			minBandwidth = Math.max(minBandwidth, bandwidth);
		}
		return minBandwidth;
	}
	/**
	 * It calculates optimal bandwidth of given component and given period
	 * by using schedulability test. 
	 *
	 * @param  theta execution time of given component.
	 * @return      optimal bandwidth.
	 * @see         none
	 */

	public double getDeadline(double theta) throws Exception {
		double minDelta = this.resPeriod + 1;
		double time = 0, tprime = 0, tprime0 = 0, tprime1 = 0;
		double lcm = C.computeLCM(this.resPeriod);
		double maxDeadline = C.computeMaxDeadline(this.resPeriod);
		double oldDemand = 0;
		double alpha = 0, delta = 0;
		int k = 0;
		double s0 = 0, s1 = -1, f0 = 0, f1 = 0;

		while (time <= lcm + maxDeadline) {
			time = time + 1;
			double demand = C.computeDBF(time, resPeriod);
			if (demand < oldDemand) {
				UserUtil.show("Demand Decreased");
				throw new Exception();
			}
			if (demand == oldDemand)
				continue;

			oldDemand = demand;
			k = (int) Math.floor(time / this.resPeriod);
			alpha = time - k * this.resPeriod;

			delta = this.resPeriod;
			f0 = Math.floor((alpha - delta + theta) / this.resPeriod);
			tprime0 = f0 * this.resPeriod + k * this.resPeriod + delta - theta;
			// tprime should not be negative ( 2010.1.27 : Jaewoo Lee)
			tprime0 = Math.max(0,tprime0);

			s0 = (theta / this.resPeriod) * (tprime0 - (delta - theta));

			if (f0 == -1) {
				delta = (alpha + theta);
				f1 = Math.floor((alpha - delta + theta) / this.resPeriod);
				tprime1 = f1 * this.resPeriod + k * this.resPeriod + delta
						- theta;
				// tprime should not be negative ( 2010.1.27 : Jaewoo Lee)
				tprime1 = Math.max(0,tprime1);

				s1 = (theta / this.resPeriod) * (tprime1 - (delta - theta));
			}

			if ((s1 > s0) && (s1 <= demand))
				tprime = tprime1;
			else
				tprime = tprime0;

			if (demand % theta == 0)
				delta = tprime + theta - demand * this.resPeriod / theta;
			else
				delta = tprime + this.resPeriod + theta
						- (demand + tprime + this.resPeriod - time)
						* this.resPeriod / theta;

			delta = Math.min(delta, this.resPeriod);

			if ((delta >= theta) && (delta < minDelta))
				minDelta = delta;
			if (minDelta == this.resPeriod + 1)
				minDelta = theta;
			//System.out.println(delta+","+minDelta);

		}

		//if (minDelta == this.resPeriod + 1)
		//	minDelta = theta;
		//System.out.println("m:"+minDelta);
		return minDelta;
	}
	/**
	 * Depending on the scheduling algorithm employed by object c, it transform 
	 * given resource model into a task with given period(EDP resource model). 
	 * @param  edp target resource model
	 * @param  period given period
	 * @return      A Task characterizing a periodic task with given period.
	 * @see         Task
	 */
	Task T_EDF(ResourceModel edp) {
		return (new Task(edp.getPeriod(), edp.getBandwidth() * edp.getPeriod(),
				edp.getPeriod() + edp.getDeadline() - edp.getBandwidth()
						* edp.getPeriod()));
	}
}
