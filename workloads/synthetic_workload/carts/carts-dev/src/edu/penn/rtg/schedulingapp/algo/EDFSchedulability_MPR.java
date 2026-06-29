package edu.penn.rtg.schedulingapp.algo;

import java.util.Vector;


import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.basic.MultiPRM;
import edu.penn.rtg.schedulingapp.basic.Workload;
import edu.penn.rtg.schedulingapp.nalgo.MultiPrmEDF;
import edu.penn.rtg.schedulingapp.nalgo.PrmAlgo;
import edu.penn.rtg.schedulingapp.util.SchException;
import edu.penn.rtg.schedulingapp.util.UserUtil;


public class EDFSchedulability_MPR {

	private int resPeriod;
	private Workload W;
	private MultiPRM RM;
	public EDFSchedulability_MPR(SchedulingComponent C, int resPeriod)
			throws Exception {

		if (!C.isEDF()) {
			UserUtil.show("The component has algorithm set to DM. Cannot continue");
			throw new SchException();
		}
		this.resPeriod = resPeriod;
		this.W=new Workload();
		Vector<Task> tasks=C.getMPRTasks();
		for(Task t:tasks) {
			W.addTask((int)t.getPeriod(),t.getExecution(),(int)t.getDeadline());
		}
	}
	public double getExec() {
		PrmAlgo ip=new MultiPrmEDF(W,resPeriod);
		RM=(MultiPRM) ip.getRes();
		//RM.display();
		return RM.getExec();
	}
	public int getM() {
		return RM.getM();
	}
}
