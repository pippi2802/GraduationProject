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
public class DMSchedulability_arinc {
	private int resPeriod;
	private SchedulingComponent C;

	/**
	 * Constructor
	 * It set target component and target period
	 * @param  C	target component
	 * @param  period given period
	 */
	public DMSchedulability_arinc(SchedulingComponent C, int resPeriod) throws Exception {
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

		double lcm = C.computeLCM(resPeriod);
		double Bandwidth = 0;

		for(int i = 0; i < this.C.getTasks(resPeriod).size(); i++){
			double exec = this.C.getTasks(resPeriod).get(i).getExecution();
			if(exec<=0) continue;

			double maxBandwidth = 0;
			Task T = this.C.getTasks(resPeriod).get(i);
			double release = T.getOffset();
			int k = 1;
			double time = 0;
			while(release <= lcm){

				time = release;
				time = time + 1;
				double minBandwidth = 1;
				while(time <= release + T.getDeadline() - T.getOffset()){

					double demand1 = C.computeRBF_arinc(0, time, i, resPeriod);
					double demand2 = C.computeRBF_arinc(release, time, i, resPeriod);
					double time2 = time - release;

				    double theta = getTheta(demand1,time);
					double bandwidth1 = theta/this.resPeriod;
					theta = getTheta(demand2,time2);
					double bandwidth2 = theta/this.resPeriod;
					minBandwidth = Math.min(minBandwidth, Math.max(bandwidth1,bandwidth2));
					time = time+1;
				}
				maxBandwidth = Math.max(maxBandwidth, minBandwidth);
				k = k+1;
				release = T.getOffset() + (k-1)*T.getPeriod();
			}
			Bandwidth = Math.max(maxBandwidth, Bandwidth);
		}
		return Bandwidth;

	}

	public double getTheta(double demand, double time){

		double util = computeUtilization();
		double minTheta = util*this.resPeriod;
		if(demand > time)
			return this.resPeriod;
		double tprime=0;
	    int k = (int)Math.floor(time/this.resPeriod);
	    double alpha = time - k*this.resPeriod;

	    double theta=this.resPeriod;
		double f0 = Math.floor((alpha-theta)/this.resPeriod);
		double tprime0= f0 * this.resPeriod + (k+1)*this.resPeriod;
		//double s0 = (theta/this.resPeriod)*tprime0;

	    theta = alpha;
		double f1 =  Math.floor((alpha-theta)/this.resPeriod);
		double tprime1 = f1 * this.resPeriod + (k+1)*this.resPeriod;
		double s1 = (theta/this.resPeriod)*tprime1;

	    if(s1>=demand)
	    	tprime = tprime1;
	    else
	    	tprime = tprime0;

	    double theta1,theta2;
    	theta1 = (demand*this.resPeriod)/tprime;
    	theta2 = (demand+tprime-time)*this.resPeriod/tprime;
    	if(tprime == 0)
    		return this.resPeriod;

    	return(Math.max(Math.min(theta1,theta2),minTheta));
	}

	public double computeUtilization(){

		double util=0;
		for(int i = 0; i < this.C.getTasks(resPeriod).size(); i++){

			Task T = this.C.getTasks(resPeriod).get(i);
			util = util+T.getExecution()/T.getPeriod();
		}
		return util;
	}
	
	
	/**
	 * It calculates optimal bandwidth of given component and given period
	 * by using schedulability test. 
	 *
	 * @param  theta execution time of given component.
	 * @return      optimal bandwidth.
	 * @see         none
	 */


	
	public double getDeadline(double bandwidth){

		double theta = bandwidth*this.resPeriod;
		double lcm = this.C.computeLCM(resPeriod);
		double Deadline = this.resPeriod;

		for(int i = 0; i < this.C.getTasks(resPeriod).size(); i++){

			double minDeadline = this.resPeriod;
			Task T = this.C.getTasks(resPeriod).get(i);
			double release = T.getOffset();
			int k = 1;
			double time = 0;
			while(release <= lcm){

				time = release;
				time = time + 1;
				double maxDeadline = theta;
				while(time <= release + T.getDeadline() - T.getOffset()){

					double demand1 = this.C.computeRBF_arinc(0, time, i, resPeriod);
					double demand2 = this.C.computeRBF_arinc(release, time, i, resPeriod);
					double time2 = time - release;

				    double deadline1 = computeDeadline(demand1,time,theta);
					double deadline2 = computeDeadline(demand2,time2,theta);
					maxDeadline = Math.max(maxDeadline, Math.min(deadline1,deadline2));
					time = time+1;
				}
				minDeadline = Math.min(minDeadline, maxDeadline);
				k = k+1;
				release = T.getOffset() + (k-1)*T.getPeriod();
			}
			Deadline = Math.min(minDeadline, Deadline);
		}
		return Deadline;
	}

	public double computeDeadline(double demand, double time, double theta){

		if(demand > time)
			return theta;

		double tprime=0;
	    int k = (int)Math.floor(time/this.resPeriod);
	    double alpha = time - k*this.resPeriod;

	    double delta=this.resPeriod;
		double f0 = Math.floor((alpha-delta)/this.resPeriod);
		double tprime0= f0 * this.resPeriod + (k+1)*this.resPeriod;

	    delta = alpha;
		double f1 =  Math.floor((alpha-delta)/this.resPeriod);
		double tprime1 = f1 * this.resPeriod + (k+1)*this.resPeriod;
		double s1 = (theta/this.resPeriod)*(tprime1-(delta-theta));

	    if((s1>=demand) && (theta <= alpha))
	    	tprime = tprime1;
	    else
	    	tprime = tprime0;

	    double delta1,delta2;
    	delta1 = tprime+theta-(demand*this.resPeriod/theta);
    	delta2 = tprime-(demand+tprime-time+theta)*this.resPeriod/theta+this.resPeriod+theta;

    	return(Math.min(Math.max(delta1,delta2),this.resPeriod));
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
