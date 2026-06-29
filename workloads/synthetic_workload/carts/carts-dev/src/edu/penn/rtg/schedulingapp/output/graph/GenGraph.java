package edu.penn.rtg.schedulingapp.output.graph;

import java.util.Vector;

import edu.penn.rtg.schedulingapp.ResourceModel;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.TreeComponent;
import edu.penn.rtg.schedulingapp.basic.DualPRM;
import edu.penn.rtg.schedulingapp.basic.MultiPRM;
import edu.penn.rtg.schedulingapp.basic.ResModel;
import edu.penn.rtg.schedulingapp.basic.Workload;
import edu.penn.rtg.schedulingapp.util.CartsProgress;
import edu.penn.rtg.schedulingapp.util.UserUtil;

public class GenGraph {
	public static boolean isApp=false;
	private static CartsProgress cartProg;
	private static String getComStr(TreeComponent C)
	{
		if (C.getAllChildren().size() != 0)
			return "comp.";
		else
			return "task";

	}
	private static String getComStr(TreeComponent C,int idx)
	{
		String comTask,idxStr;
		comTask=getComStr(C);
		if(idx==1) 
			idxStr="1st";
		else if(idx==2) 
			idxStr="2nd";
		else if(idx==3) 
			idxStr="3rd";
		else
			idxStr=idx+"th";
		return idxStr+" highest prio. "+comTask;
	}

	/**
	 * Generates the Graph for the Analysis Output
	 * 
	 * @param comp
	 * @throws Exception 
	 */
	public static void drawGraph(TreeComponent tc) throws Exception {
		//System.out.println(prevAlgo);
		if (!(tc.isProcessed())) {
			UserUtil.showErr("Please process the Component first");
			return;
		}
		SchedulingComponent comp=(SchedulingComponent) tc.getSchCom();
		Runtime r = Runtime.getRuntime();
		r.gc();		
		String prevAlgo=comp.getProcessedAlgo();
		ResourceModel rm = tc.getResourceModelList().getResourceModels().get(0);
		if(comp.getAlgorithm().equals("EDF")) {
			if(prevAlgo.equals("DPRM")) {
				drawDPRM(comp,rm);
			} else if(prevAlgo.equals("MPR")) {
				drawMPR(comp,rm);
			} else {
				drawEDF(comp,rm,prevAlgo);
			} 
		}
		else {
			Vector<Task> tasks =comp.getTasks((int) comp.getMaxPeriod());
			int start_idx=0;
			for(int i=0;i<tasks.size();i++) {
				if (tasks.get(i).getPeriod()==0||tasks.get(i).getExecution()==0)
					start_idx++;
			}
			String comStr=getComStr(tc);
			String str="Which priority "+comStr+" will you see sbf/rbf at ? (0: all , 1-"+(tasks.size()-start_idx)+")";
			int val=UserUtil.select(str, 0, tasks.size());
			if(val==-1){
				return;
			}
			if(val==0) {
				cartProg=new CartsProgress((tasks.size()-start_idx)*3);
				cartProg.setVisible(true);
				for(int i=start_idx;i<tasks.size();i++) {
					comStr=getComStr(tc,(i-start_idx+1));
					drawFP(comp,rm,i,comStr);
				}
				cartProg.end();
			}
			else {
				cartProg=new CartsProgress(3);
				cartProg.setVisible(true);
				comStr=getComStr(tc,val);
				drawFP(comp,rm,val+start_idx-1,comStr);
				cartProg.end();
			}
		}
	}
	public static void drawFP(SchedulingComponent comp,ResourceModel rm,int val,String comStr)
	{
		String prevAlgo=comp.getProcessedAlgo();
		if(prevAlgo.equals("SIRAP")){
			drawSirap(comp,rm,"PRM",val,comStr);
		} 
		else if(prevAlgo.equals("ARINC")){
			drawArinc(comp,rm,val,comStr);
		}
		else{
			drawRM(comp,rm,prevAlgo,val,comStr);
		}
	}
	public static void drawRM(SchedulingComponent C,ResourceModel rm, String rmStr,int i,String comStr)
	{
		Vector<Task> tasks =C.getTasks((int) C.getMaxPeriod());
		if (tasks.get(i).getPeriod()==0||tasks.get(i).getExecution()==0)
			return;
		CartsGraph g = new CartsGraph();
		g.init("SBF/RBF of "+ comStr+" ("+rmStr +")",i+1,true);
		int limit=(int)tasks.get(i).getPeriod()+1;
		double fpx=findPoint(rm,C,i,limit);
		if(limit<fpx*2) limit=(int)(fpx*2);
		g.setLimit(limit);
		g.circle(fpx,rm.computeSBF(fpx));
		cartProg.increment();
		g.drawSBF(rm);
		cartProg.increment();
		g.drawRBF(C,i);
		g.show();		
		cartProg.increment();
	}

	public static void drawArinc(SchedulingComponent C,ResourceModel rm,int i,String comStr)
	{
		//System.out.println("ww1");
		Vector<Task> tasks =C.getTasks((int) C.getMaxPeriod());
		if (tasks.get(i).getPeriod()==0||tasks.get(i).getExecution()==0)
			return;
		CartsGraph g;
		g = new CartsGraph();
		g.init("SBF/RBF of "+ comStr+" (EDP + ARINC)",i+1,true);
		if(isApp)
			g.initApp();

		int limit=(int)tasks.get(i).getPeriod()+1;
		double fpx=findPoint(rm,C,i,limit);
		if(limit<fpx*2) {
			if(fpx>100000){
				limit=(int)(fpx*1.2);
			}
			else if(fpx>50000) {
				limit=(int)(fpx*1.5);
			}
			else if(fpx>25000) {
				limit=(int)(fpx*1.7);
			}
			else {
				limit=(int)(fpx*2);
			}
		}
		g.setLimit(limit);
		g.circle(fpx,rm.computeSBF_Arinc(fpx));
		//System.out.println(limit);
		cartProg.increment();
		g.drawSBF_Arinc(rm);
		cartProg.increment();
		//System.out.println("ww2,5");
		g.drawRBF(C,i);
		//System.out.println("ww3");
		g.show();		
		cartProg.increment();
	}
	public static void drawSirap(SchedulingComponent C,ResourceModel rm, String rmStr,int i,String comStr)
	{
		Vector<Task> tasks =C.getTasks((int) C.getMaxPeriod());
		if (tasks.get(i).getPeriod()==0||tasks.get(i).getExecution()==0)
			return;
		CartsGraph g;
		g = new CartsGraph();
		g.init("SBF/RBF of "+ comStr+" (PRM + SIRAP)",i+1,true);
		if(isApp)
			g.initApp();
		
		int limit=(int)tasks.get(i).getPeriod()+1;
		double fpx=findPointSIRAP(rm,C,i,limit);
		if(limit<fpx*2) limit=(int)(fpx*2);
		g.setLimit(limit);
		g.circle(fpx,rm.computeSBF(fpx));
		cartProg.increment();
		g.drawSBF(rm);
		cartProg.increment();
		g.drawSIRAP(C,i);
		g.show();		
		cartProg.increment();
	}


	public static void drawEDF(SchedulingComponent C,ResourceModel rm, String rmStr)
	{
		CartsGraph g;
		g = new CartsGraph();
		g.init("SBF/DBF"+" ("+rmStr +" interface)",1,false);
		if(isApp)
			g.initApp();

		int limit=(int)C.computeLCM((int)C.getMaxPeriod());
		Vector<Task> tasks =C.getTasks((int) C.getMaxPeriod());
		//System.out.println(limit+","+(int)tasks.get(0).getPeriod());
		if(limit==(int)tasks.get(0).getPeriod()){
			limit=2*limit;
		}
		g.setLimit(limit+1);
		//System.out.println(limit);
		//g.setLimit(200);
		g.drawSBF(rm);
		g.drawDBF(C);
		g.findTight(C,rm);
		g.show();		
	}
	
	public static void drawDPRM(SchedulingComponent C,ResourceModel rm) throws Exception
	{

		Workload wl=new Workload();
		Vector<Task> tasks=C.getDPRMTasks();
		for(Task t:tasks) {
			wl.addTask((int)t.getPeriod(),(int)t.getExecution(),(int)t.getDeadline());
		}
		//wl.display();
		ResModel res=new DualPRM((int)rm.getPeriod(),(int)rm.getBandwidth(),rm.period2,rm.exec2);
		//res.display();
		NCartsGraph g = new NCartsGraph();
		g.init("SBF/DBF (DPRM interface)",1,false);
		if(isApp)
			g.initApp();
		
		g.setRange(wl);
		g.drawSBF(res);
		g.drawDBF(wl);
		g.setXLimitEDF(res,wl);
		g.show();

		
	}
	public static void drawMPR(SchedulingComponent C,ResourceModel rm) throws Exception
	{
		Workload wl=new Workload();
		Vector<Task> tasks=C.getTasks(C.getSize((int) C.getMaxPeriod()));
		for(Task t:tasks) {
			wl.addTask((int)t.getPeriod(),(int)t.getExecution(),(int)t.getDeadline());
		}
		MultiPRM res=new MultiPRM(rm.cpus,rm.period2,rm.exec2);
		//res.display();
		NCartsGraph g;
		for(int i=0;i<tasks.size();i++){
			if (tasks.get(i).getPeriod()==0||tasks.get(i).getExecution()==0)
				continue;
			g = new NCartsGraph();
			int max_a=(int)wl.getUpperBoundArr(i,res);

			g.init("SBF/DBF at i="+(i+1)+" (MPR interface)",i+1,true);
			if(isApp)
				g.initApp();
			g.setRange(wl.deadline(i),max_a+wl.deadline(i));
			g.drawSBF(res);
			g.drawDBF_MPR(wl,res.getM(),i);
			//g.setXLimitEDF(res,wl);
			g.show();
		}
	}

	
	public static double findPoint(ResourceModel rm, SchedulingComponent C,int ind,int limit){
		int resPeriod=(int)C.getMaxPeriod();
		for(int t=0;t<=limit;t++)
		{
			
			if(rm.computeSBF(t)!=0&&C.computeRBF((double)t,ind,resPeriod)<=rm.computeSBF(t))
				return t;
		}
		//System.out.println(C.computeRBF((double)limit,ind,resPeriod)+","+rm.computeSBF(limit));
		return limit;
	}
	public static double findPointArinc(ResourceModel rm, SchedulingComponent C,int ind,int limit){
		int resPeriod=(int)C.getMaxPeriod();
		for(int t=0;t<=limit;t++)
		{
			
			if(rm.computeSBF_Arinc(t)!=0&&C.computeRBF((double)t,ind,resPeriod)<=rm.computeSBF_Arinc(t))
				return t;
		}
		//System.out.println(C.computeRBF((double)limit,ind,resPeriod)+","+rm.computeSBF(limit));
		return limit;
	}
	public static double findPointSIRAP(ResourceModel rm, SchedulingComponent C,int ind,int limit){
		int resPeriod=(int)C.getMaxPeriod();
		for(int t=0;t<=limit;t++)
		{
			
			if(rm.computeSBF(t)!=0&&C.computeRBF_SIRAP((double)t,ind,resPeriod)<=rm.computeSBF(t))
				return t;
		}
		//System.out.println(C.computeRBF((double)limit,ind,resPeriod)+","+rm.computeSBF(limit));
		return limit;
	}
}
