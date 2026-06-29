package edu.penn.rtg.schedulingapp.algo;


import edu.penn.rtg.schedulingapp.ResourceModel;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.util.SchException;
import edu.penn.rtg.schedulingapp.util.UserUtil;
/**
 * Compute optimal bandwidth and deadline (DM, EDP).
 * this class has two main function<P>
 * 1. Compute optimal bandwidth and deadline <BR>
 * Using schedulability test, it compute optimal bandwidth and deadline<P>
 * 2. transform a resource model  into a single task<P>
 * supported resource model : ARINC, EDP <BR>
 * supported scheduling algorithm : DM
 * <P>
 * @author      
 * @version     1.0
 * @since       1.0
 */
public class DMSchedulability_edp {
	private int resPeriod;
	private SchedulingComponent C;

	/**
	 * Constructor
	 * It set target component and target period
	 * @param  C	target component
	 * @param  period given period
	 */
	public DMSchedulability_edp(SchedulingComponent C, int resPeriod) throws Exception {
		if (!C.isDM()) {
			UserUtil.show("The component has algorithm set to EDF. Cannot continue");
			throw new SchException();
		}
		this.C = C;
		this.resPeriod = resPeriod;
	}

	/**
	 * It calculates optimal bandwidth of given component and given period
	 * by using schedulability test. 
	 *
	 * @return      optimal bandwidth.
	 * @see         none
	 */
	public double getBandwidth() {
		double maxBandwidth = 0;
		for (int index = 0; index < this.C.getSize(resPeriod); index++) {

			double minBandwidth = 100;
			double deadline = this.C.getTasks(resPeriod).get(index)
					.getDeadline();
			double exec = this.C.getTasks(resPeriod).get(index).getExecution();
			if(exec<=0) continue;
			double time = deadline;
			double oldDemand = 0;
			int k = 0;
			double theta = 0, theta1 = 0, theta2 = 0;

			if (time <= 0)
				minBandwidth = 0;

			while (time > 0) {
				double demand = C.computeRBF(time, index, resPeriod);
				if (demand == oldDemand) {
					time = time - 1;
					continue;
				}

				oldDemand = demand;

				k = (int) Math.floor(time / this.resPeriod);

				theta1 = demand / k;
				theta2 = (demand + (k + 1) * this.resPeriod - time) / (k + 1);

				if ((time - this.resPeriod + theta2 - k * this.resPeriod) > 0)
					theta = theta2;
				else
					theta = theta1;

				double bandwidth = theta / this.resPeriod;

				minBandwidth = Math.min(minBandwidth, bandwidth);
				time = time - 1;
			}
			maxBandwidth = Math.max(maxBandwidth, minBandwidth);
		}
		return maxBandwidth;
	}

	/**
	 * It calculates optimal bandwidth of given component and given period
	 * by using schedulability test. 
	 *
	 * @param  theta execution time of given component.
	 * @return      optimal bandwidth.
	 * @see         none
	 */

	public double getDeadline(double theta) {
		double minDelta = this.resPeriod;
		for (int index = 0; index < this.C.getSize(resPeriod); index++) {
			double deadline = this.C.getTasks(this.resPeriod).get(index)
					.getDeadline();
			double time = deadline, tprime = 0, tprime0 = 0, tprime1 = 0;
			double oldDemand = 0;
			double maxDelta = 0;

			double alpha = 0, delta = 0;
			int k = 0;
			double s0 = 0, s1 = -1, f0 = 0, f1 = 0;
			if(this.resPeriod>deadline) {
				double demand = C.computeRBF(time, index, resPeriod);
				double wc_rel=resPeriod-theta;
				double res_start=deadline-demand;
				maxDelta=res_start+theta-wc_rel;
				//System.out.println("dmax:("+index+")"+maxDelta);
				time=0; // to skip while
			}
			while (time > 0) {
				double demand = C.computeRBF(time, index, resPeriod);
				if (demand == oldDemand) {
					time = time - 1;
					continue;
				}
				//System.out.println(time+","+demand);
				oldDemand = demand;
				k = (int) Math.floor(time / this.resPeriod);
				alpha = time - k * this.resPeriod;

				delta = this.resPeriod;
				f0 = Math.floor((alpha - delta + theta) / this.resPeriod);
				tprime0 = f0 * this.resPeriod + k * this.resPeriod + delta
						- theta;
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
				
				if (demand % theta == 0) {
					delta = tprime + theta - demand * this.resPeriod / theta;
				}
				else{
					delta = tprime + this.resPeriod + theta
							- (demand + tprime + this.resPeriod - time)
							* this.resPeriod / theta;
				}

				delta = Math.min(delta, this.resPeriod);

				if ((delta >= theta) && (delta > maxDelta))
					maxDelta = delta;
				//System.out.println(delta);
			}
			if (maxDelta == 0.0)
				maxDelta = theta;

			minDelta = Math.min(minDelta, maxDelta);
			//System.out.println("max:("+index+")"+maxDelta);
		}
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

	Task T_DM(ResourceModel edp, int period) {
		int rperiod = (int) edp.getPeriod();
		double rtheta = edp.getBandwidth() * edp.getPeriod();
		double rdelta = edp.getDeadline();
		if (period >= rperiod) {
			return (new Task(period, rtheta + (period - rperiod) * rtheta
					/ rdelta, period));
		} else {
			if (rperiod % period == 0) {
				return (new Task(period, rtheta * period / rperiod, period));
			} else {

				int k = (int) Math.floor(rperiod / period) + 1;
				double beta = period - rperiod / k;
				int lbd = (int) Math.floor((rdelta - rtheta) / (k * beta)) + 1;
				int ubd = lbd + period;
				double theta = rtheta / k + beta * rtheta / rperiod;

				for (int n = lbd; n <= ubd; n++) {
					int l = (int) Math.floor((n * k * beta - rdelta + rtheta)
							/ period);
					double gamma = (n * k * beta - rdelta + rtheta) - l
							* period;
					if (gamma >= n * rtheta / (n * k - l - 1)) {
						theta = n * rtheta / (n * k - l - 1);
						break;
					}
				}
				return (new Task(period, theta, period));
			}
		}
	}

	/**
	 * Depending on the scheduling algorithm employed by object c, it transform 
	 * given resource model into a task with given period(ARINC resource model). 
	 * @param  periodic target resource model
	 * @return      A Task characterizing a periodic task with given period.
	 * @see         Task
	 */

	Task T_DM_arinc(ResourceModel periodic) {
		int rperiod = (int) periodic.getPeriod();
		double rtheta = periodic.getBandwidth() * periodic.getPeriod();
		return (new Task(rperiod, rtheta, rperiod));
	}
}
