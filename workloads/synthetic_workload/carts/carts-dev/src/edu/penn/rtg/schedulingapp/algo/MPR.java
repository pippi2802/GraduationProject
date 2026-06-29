package edu.penn.rtg.schedulingapp.algo;



import edu.penn.rtg.schedulingapp.ResourceModel;
import edu.penn.rtg.schedulingapp.ResourceModelList;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.TaskList;
import edu.penn.rtg.schedulingapp.TreeComponent;
import edu.penn.rtg.schedulingapp.util.CartsProgress;
import edu.penn.rtg.schedulingapp.util.UserUtil;

public class MPR {
	CartsProgress cp;
	public static boolean check(TreeComponent comp)
	{
		if (comp.getAllChildren().size() != 0) {
			for (TreeComponent c : comp.getAllChildren()) {
				if(!MPR.check(c)) 
					return false;
			}
		}
		if(comp.getSchCom().isEDF())
			return true;
		else
			return false;
	}
	public void start(TreeComponent comp){
		int size=comp.getChildSize()+2;
		cp=new CartsProgress(size);
		cp.setVisible(true);
	}
	public void end(){
		cp.end();
	}
	
	protected ResourceModel generateInterface(int period, SchedulingComponent C)
			throws Exception {

		if (C.isEDF()) {
			EDFSchedulability_MPR schedulability 
				= new EDFSchedulability_MPR(C, period);
			double exec = schedulability.getExec();
			int m = schedulability.getM();
			ResourceModel rm = new ResourceModel(0,0,0);
			rm.period2=period;
			rm.exec2=exec;
			rm.cpus=m;
			rm.type=ResourceModel.MPR;
			System.out.println("xm-debug: generateInterface(): (period, execution,m) "+rm.period2 + ","+rm.exec2+","+rm.cpus);
			return rm;
		} 
		else
		{
			//System.out.println("TODO");
			UserUtil.show("Computing MPR interface only works with EDF. Cannot continue");
			throw new Exception();
		}
	}

	public void abstractionProcedure(TreeComponent tc) throws Exception {
		if (tc.getAllChildren().size() != 0) {
			for (TreeComponent comp : tc.getAllChildren()) {
				abstractionProcedure(comp);
			}
		}
		cp.increment();
		SchedulingComponent c=(SchedulingComponent) tc.getSchCom();
		ResourceModelList list = new ResourceModelList();
		TaskList processed = new TaskList();
		for (int i = (int) c.getMinPeriod(); i <= (int) c
				.getMaxPeriod(); i++) {
			ResourceModel rm = generateInterface(i, c);
			list.getResourceModelArray().add(rm);
			//transfer the interface to m' interface tasks with almost equal utilization
			double alpha=rm.exec2-rm.cpus*(int)(Math.floor(rm.exec2/rm.cpus)); //Transfer the interface to m' interface tasks. In Defintion 2 in 09rtsj-virtual-clustering paper
			int k=(int) Math.floor(alpha);
			double exec=0;
			Task t;
			int num=0;
			
			for(int j=0;j<k;j++) {
				exec=(int) (Math.floor(rm.exec2/rm.cpus)+1);
				t=new Task(rm.period2,exec,rm.period2);
				//t.print();
				processed.getTasks().add(t);
				num++;
			}
			//Debug.prn(k);
			//interface task k
			if(k == 0){
				exec= Math.floor(rm.exec2/rm.cpus)+alpha-0; 	// 0 is for k*Math.floor(alpha/k) when k =0;
			}else{
				exec= Math.floor(rm.exec2/rm.cpus)+alpha-k*Math.floor(alpha/k);
			}
			
			t=new Task(rm.period2,exec,rm.period2);
			//t.print();
			processed.getTasks().add(t);
			num++;

			for(int j=num;j<rm.cpus;j++) {
				exec=(int) (Math.floor(rm.exec2/rm.cpus));
				t=new Task(rm.period2,exec,rm.period2);
				//t.print();
				processed.getTasks().add(t);
			}

			//end interface transformation to interface tasks
			//System.out.println(processed.toString());
		}
		//System.out.println(processed.toString());
		tc.setProcessedTaskList(processed);
		tc.setResourceModelList(list);
		if (tc.hasParentComp()) {
			//System.out.println("Yes");
			tc.getParentComp().getChildrenToTaskTable().put(tc, processed);
			//System.out.println(tl.size());
			
		}
		tc.setProcessed(true);
	}
}